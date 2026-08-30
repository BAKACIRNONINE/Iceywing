from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from .config import ProjectConfig
from .runtime import identify, is_alive as runtime_is_alive, terminate_tree
from .verification import VerifyResult, merge_results, run_verification
from .util import (
    IceywingError,
    abort_progress,
    command_exists,
    is_quiet,
    is_verbose,
    progress as _render_progress,
    progress_note,
    run,
    run_live_logged,
    run_logged,
    say,
    sha256_file,
    sha256_text,
    shell_command,
    state_home,
    tick_progress,
)


def progress(index: int, total: int, status: str, label: str) -> None:
    """Use live progress interactively and plain rows for logs and CI."""
    _render_progress(index, total, status, label, live=True)


def _has_just(root: Path) -> bool:
    return (root / "justfile").exists() or (root / "Justfile").exists()


def _just_recipes(config: ProjectConfig) -> set[str]:
    if not (_has_just(config.root) and command_exists("just")):
        return set()
    result = run(["just", "--color", "never", "--summary"], cwd=config.root, check=False)
    if result.returncode != 0:
        return set()
    return set((result.stdout or "").split())


def _task(config: ProjectConfig, name: str) -> list[str] | None:
    if name in config.tasks:
        return shell_command(config.tasks[name])
    if name in _just_recipes(config):
        return ["just", "--color", "never", name]
    return None


def detect_runtimes(config: ProjectConfig) -> list[str]:
    if config.runtimes:
        return list(dict.fromkeys(config.runtimes))
    if config.environment_type != "auto":
        return [config.environment_type]

    result: list[str] = []
    if (config.root / "package.json").exists():
        result.append("node")
    if (config.root / "pyproject.toml").exists():
        result.append("python")
    if (config.root / "Cargo.toml").exists():
        result.append("rust")
    return result or ["generic"]


def detect_type(config: ProjectConfig) -> str:
    return detect_runtimes(config)[0]


def run_task(config: ProjectConfig, name: str) -> bool:
    cmd = _task(config, name)
    if not cmd:
        return False
    if not is_quiet():
        print("->", " ".join(cmd))
    run(cmd, cwd=config.root, capture=False)
    return True


def _checks(config: ProjectConfig) -> tuple[list[tuple[str, bool, str]], list[str]]:
    runtimes = detect_runtimes(config)
    checks = [
        ("Git", command_exists("git"), shutil.which("git") or "missing"),
        ("just", command_exists("just"), shutil.which("just") or "optional but recommended"),
    ]

    if "node" in runtimes:
        checks += [
            ("Node", command_exists("node"), shutil.which("node") or "missing"),
            ("npm", command_exists("npm"), shutil.which("npm") or "missing"),
        ]
    if "python" in runtimes:
        checks += [
            ("Python", command_exists("python") or command_exists("python3"), "required"),
            ("uv", command_exists("uv"), shutil.which("uv") or "optional but recommended"),
        ]
    if "rust" in runtimes:
        checks.append(("Cargo", command_exists("cargo"), shutil.which("cargo") or "missing"))
    return checks, runtimes


def doctor(config: ProjectConfig, *, quiet: bool = False) -> bool:
    checks, runtimes = _checks(config)
    ok = True

    if not quiet:
        print(f"* Environment doctor - {config.name}")
        print(f"Runtimes: {', '.join(runtimes)}\n")

    for name, passed, detail in checks:
        if not quiet:
            mark = "[OK]" if passed else "[WARN]"
            print(f"{mark} {name:<12} {detail}")
        if name not in {"just", "uv"} and not passed:
            ok = False

    if not quiet:
        optional = [("mise", "mise"), ("StGit", "stg"), ("git-cliff", "git-cliff")]
        print("\nOptional adapters")
        for label, cmd in optional:
            print(f"{'[OK]' if command_exists(cmd) else '[--]'} {label}")

    custom = _task(config, "doctor")
    if custom:
        if quiet:
            result = run(custom, cwd=config.root, check=False)
            if result.returncode != 0:
                return False
        else:
            print("\nProject doctor")
            result = run(custom, cwd=config.root, check=False, capture=False)
            ok = ok and result.returncode == 0
    return ok


def _environment_state_path(config: ProjectConfig) -> Path:
    key = sha256_text(str(config.root.resolve()).lower())[:16]
    return state_home() / "projects" / key / "environment.json"


def _setup_inputs(config: ProjectConfig) -> list[Path]:
    names = {
        "iceywing.toml",
        "justfile",
        "Justfile",
        "package.json",
        "package-lock.json",
        "npm-shrinkwrap.json",
        "pyproject.toml",
        "uv.lock",
        "requirements.txt",
        "requirements-dev.txt",
        "poetry.lock",
        "pdm.lock",
        "Pipfile",
        "Pipfile.lock",
        "Cargo.toml",
        "Cargo.lock",
        ".nvmrc",
        ".python-version",
    }
    excluded = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "coverage",
        ".pytest_cache",
        ".cache",
    }

    def relevant(path: Path) -> bool:
        rel = path.relative_to(config.root)
        if path.name in names:
            return True
        return (
            bool(rel.parts)
            and rel.parts[0] == "scripts"
            and path.name.lower().startswith("setup")
            and path.suffix.lower() in {".js", ".mjs", ".cjs", ".py", ".ps1", ".sh"}
        )

    result: list[Path] = []
    if (config.root / ".git").exists() and command_exists("git"):
        tracked = run(["git", "ls-files", "-z"], cwd=config.root, check=False)
        if tracked.returncode == 0:
            for rel_text in (tracked.stdout or "").split("\0"):
                if not rel_text:
                    continue
                path = config.root / rel_text
                if path.is_file() and relevant(path):
                    result.append(path)
            for filename in ("iceywing.toml", "justfile", "Justfile"):
                path = config.root / filename
                if path.is_file():
                    result.append(path)
            return sorted(set(result), key=lambda item: item.as_posix())

    for base, dirs, files in os.walk(config.root):
        dirs[:] = [name for name in dirs if name not in excluded]
        base_path = Path(base)
        for filename in files:
            path = base_path / filename
            if relevant(path):
                result.append(path)
    return sorted(set(result), key=lambda item: item.as_posix())


def _environment_signature(config: ProjectConfig) -> str:
    pieces = [f"root={config.root.resolve()}"]
    for path in _setup_inputs(config):
        rel = path.relative_to(config.root).as_posix()
        pieces.append(f"{rel}:{sha256_file(path)}")
    return sha256_text("\n".join(pieces))


def _load_environment_state(config: ProjectConfig) -> dict[str, object] | None:
    path = _environment_state_path(config)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _save_environment_state(config: ProjectConfig, signature: str) -> None:
    path = _environment_state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "root": str(config.root.resolve()),
                "signature": signature,
                "updated_at": int(time.time()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def up(config: ProjectConfig, *, fresh: bool = False, repair: bool = False) -> None:
    started = time.monotonic()
    say("* Iceywing Environment\n")
    progress(1, 3, "[OK]", f"Check project - {config.name}")

    signature = _environment_signature(config)
    state = _load_environment_state(config)
    cached_signature = str(state.get("signature", "")) if state else ""

    healthy = False if fresh else doctor(config, quiet=True)
    unchanged = cached_signature == signature

    if not fresh and healthy and (unchanged or state is None or repair):
        _save_environment_state(config, signature)
        label = "Environment unchanged" if unchanged else "Environment already ready"
        progress(2, 3, "[OK]", label)
        elapsed = time.monotonic() - started
        progress(3, 3, "[OK]", "Ready")
        if is_quiet():
            print(f"[OK] ready {elapsed:.1f}s")
        else:
            print(f"\n[OK] Environment ready in {elapsed:.1f}s")
        return

    task = _task(config, "setup")
    progress(2, 3, "[....]", "Setup environment")
    if task:
        display = config.tasks.get("setup") or " ".join(task)
        if not is_quiet():
            progress_note(f"      -> {display}")
        result = run_logged(
            task,
            cwd=config.root,
            label="Installing project environment",
            log_prefix="env-up",
            heartbeat=True,
        )
    else:
        runtimes = detect_runtimes(config)
        if "node" in runtimes:
            if not command_exists("npm"):
                raise IceywingError("npm is required.")
            cmd = ["npm", "ci"] if (config.root / "package-lock.json").exists() else ["npm", "install"]
            if not is_quiet():
                progress_note(f"      -> {' '.join(cmd)}")
            result = run_logged(
                cmd,
                cwd=config.root,
                label="Installing Node dependencies",
                log_prefix="env-node",
                heartbeat=True,
            )
        else:
            result = None
        if "python" in runtimes:
            if command_exists("uv") and (config.root / "pyproject.toml").exists():
                cmd = ["uv", "sync"]
                if not is_quiet():
                    progress_note(f"      -> {' '.join(cmd)}")
                result = run_logged(
                    cmd,
                    cwd=config.root,
                    label="Installing Python dependencies",
                    log_prefix="env-python",
                    heartbeat=True,
                )
            elif runtimes == ["python"]:
                raise IceywingError("Python project has no setup task and uv is not installed.")
        if runtimes == ["generic"]:
            raise IceywingError("No setup task found. Define `just setup` or [tasks].setup.")

    setup_elapsed = getattr(result, "iceywing_elapsed", None) if result else None
    suffix = f" ({setup_elapsed:.1f}s)" if setup_elapsed is not None else ""
    progress(2, 3, "[OK]", f"Setup environment{suffix}")

    if not doctor(config, quiet=True):
        raise IceywingError(
            "Environment setup finished, but health checks still fail.\n"
            "Run `iceywing doctor` for details."
        )

    _save_environment_state(config, signature)
    elapsed = time.monotonic() - started
    progress(3, 3, "[OK]", "Ready")
    if is_quiet():
        print(f"[OK] ready {elapsed:.1f}s")
    else:
        print(f"\n[OK] Environment ready in {elapsed:.1f}s")



def _run_state_path(config: ProjectConfig) -> Path:
    key = sha256_text(str(config.root.resolve()).lower())[:16]
    return state_home() / "projects" / key / "run.json"


def _load_run_state(config: ProjectConfig) -> dict[str, object] | None:
    path = _run_state_path(config)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _save_run_state(
    config: ProjectConfig,
    *,
    pid: int,
    create_time: float | None = None,
    services: dict[str, str] | None = None,
    started_at: int | None = None,
) -> None:
    path = _run_state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "root": str(config.root.resolve()),
                "pid": int(pid),
                "create_time": create_time,
                "started_at": int(started_at or time.time()),
                "services": services or {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _clear_run_state(config: ProjectConfig) -> None:
    try:
        _run_state_path(config).unlink()
    except FileNotFoundError:
        pass


def _process_exists(pid: int, create_time: float | None = None) -> bool:
    return runtime_is_alive(pid, create_time)


def _terminate_pid_tree(pid: int, create_time: float | None = None) -> None:
    terminate_tree(pid, create_time=create_time, timeout=5.0)


def _tracked_run(config: ProjectConfig) -> tuple[dict[str, object] | None, bool]:
    state = _load_run_state(config)
    if not state:
        return None, False
    try:
        pid = int(state.get("pid", 0))
    except (TypeError, ValueError):
        pid = 0
    raw_create_time = state.get("create_time")
    try:
        create_time = float(raw_create_time) if raw_create_time is not None else None
    except (TypeError, ValueError):
        create_time = None
    alive = _process_exists(pid, create_time)
    if not alive:
        _clear_run_state(config)
    return state, alive


def _print_services(services: dict[str, str]) -> None:
    for name in ("Frontend", "API", "Recorder", "Planner"):
        value = services.get(name)
        if value:
            print(f"[OK] {name:<10} {value}")


def stop_project(config: ProjectConfig, *, quiet: bool = False) -> None:
    state, alive = _tracked_run(config)
    if not state or not alive:
        if not quiet and not is_quiet():
            print("[OK] Project not running")
        return

    pid = int(state.get("pid", 0))
    # Mark the run as intentionally stopping before terminating the tree so the
    # foreground `iceywing run` process does not report the expected signal exit
    # as a runtime failure.
    stopping_state = dict(state)
    stopping_state["stopping"] = True
    path = _run_state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stopping_state, indent=2) + "\n", encoding="utf-8")

    if not quiet and not is_quiet():
        print("* Iceywing Stop\n")
        progress(1, 1, "[....]", "Stop project")
    raw_create_time = state.get("create_time")
    try:
        create_time = float(raw_create_time) if raw_create_time is not None else None
    except (TypeError, ValueError):
        create_time = None
    _terminate_pid_tree(pid, create_time)

    deadline = time.monotonic() + 5.0
    while _process_exists(pid, create_time) and time.monotonic() < deadline:
        tick_progress()
        time.sleep(0.1)
    _clear_run_state(config)

    if not quiet and not is_quiet():
        progress(1, 1, "[OK]", "Stop project")
        print("\n[OK] Project stopped")


def _runtime_summary(line: str, seen: set[tuple[str, str]], services: dict[str, str] | None = None) -> bool:
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", line).strip()
    if not text:
        return False

    entries: list[tuple[str, str]] = []
    ready = False

    if "NeuroScape study recorder:" in text:
        entries.append(("Recorder", text.split("NeuroScape study recorder:", 1)[1].strip()))
        ready = True
    elif text.startswith("OpenAI planner:"):
        entries.append(("Planner", text.split(":", 1)[1].strip()))
    elif "Uvicorn running on " in text:
        value = text.split("Uvicorn running on ", 1)[1].split(" ", 1)[0].strip()
        entries.append(("API", value))
        ready = True
    else:
        local = re.search(r"\bLocal:\s+(https?://\S+)", text)
        if local:
            entries.append(("Frontend", local.group(1)))
            ready = True

    if not entries and re.search(r"\b(ready|listening|running on|server started)\b", text, re.IGNORECASE):
        ready = True

    if not entries and re.search(r"(EADDRINUSE|address already in use|\bERROR\b|\bFATAL\b|Traceback)", text, re.IGNORECASE):
        detail = (
            "port already in use; another instance may be running"
            if re.search(r"EADDRINUSE|address already in use", text, re.IGNORECASE)
            else "reported an error; use --verbose or inspect the run log"
        )
        key = ("Runtime", detail)
        if key not in seen:
            seen.add(key)
            progress_note(f"[WARN] {key[0]:<10} {key[1]}")

    for entry in entries:
        if services is not None:
            services[entry[0]] = entry[1]
        if entry in seen:
            continue
        seen.add(entry)
        progress_note(f"[OK] {entry[0]:<10} {entry[1]}")
    return ready


def run_project(config: ProjectConfig, *, replace: bool = False) -> None:
    cmd = _task(config, "run")
    if not cmd:
        raise IceywingError("No run task. Define `just run` or [tasks].run.")

    existing, alive = _tracked_run(config)
    if alive and existing:
        if replace:
            stop_project(config, quiet=True)
        else:
            if not is_quiet():
                print("* Iceywing Run\n")
                progress(1, 2, "[OK]", f"Check project - {config.name}")
                progress(2, 2, "[OK]", "Already running")
                print("\n[OK] Project already running")
                services = existing.get("services", {})
                if isinstance(services, dict):
                    _print_services({str(k): str(v) for k, v in services.items()})
                print("Use `iceywing run --replace` to restart it.")
            return

    started = time.monotonic()
    started_at = int(time.time())
    if not is_quiet():
        print("* Iceywing Run\n")
    progress(1, 2, "[OK]", f"Check project - {config.name}")
    progress(2, 2, "[....]", "Start project")
    if not is_quiet() and not is_verbose():
        display = config.tasks.get("run") or " ".join(cmd)
        progress_note(f"      -> {display}")

    seen: set[tuple[str, str]] = set()
    services: dict[str, str] = {}
    announced = False
    root_pid = 0
    root_create_time: float | None = None

    def on_start(process: subprocess.Popen[bytes]) -> None:
        nonlocal root_pid, root_create_time
        root_pid = process.pid
        identity = identify(root_pid)
        root_create_time = identity.create_time if identity else None
        _save_run_state(
            config,
            pid=root_pid,
            create_time=root_create_time,
            services=services,
            started_at=started_at,
        )

    def on_line(line: str) -> bool:
        nonlocal announced
        before = dict(services)
        ready = _runtime_summary(line, seen, services)
        if root_pid and services != before:
            _save_run_state(
                config,
                pid=root_pid,
                create_time=root_create_time,
                services=services,
                started_at=started_at,
            )
        if ready and not announced:
            announced = True
            elapsed = time.monotonic() - started
            progress(2, 2, "[OK]", f"Running ({elapsed:.1f}s)")
            print("\n[OK] Project running - Ctrl+C to stop")
        return announced

    try:
        result = run_live_logged(
            cmd,
            cwd=config.root,
            label="Project process",
            log_prefix="run",
            on_line=on_line,
            on_start=on_start,
        )
    except KeyboardInterrupt:
        if not is_quiet():
            abort_progress("[OK]")
            print("\n[OK] Project stopped")
        return
    except IceywingError:
        # Another `iceywing stop` may terminate the tracked process tree before
        # this foreground process notices. A stopping marker makes that expected
        # signal exit a normal lifecycle event instead of a runtime failure.
        current_state = _load_run_state(config)
        if root_pid and (current_state is None or current_state.get("stopping") is True):
            if not is_quiet():
                abort_progress("[OK]")
                print("\n[OK] Project stopped")
            return
        raise
    finally:
        _clear_run_state(config)

    if not is_quiet():
        elapsed = getattr(result, "iceywing_elapsed", time.monotonic() - started)
        if not announced:
            progress(2, 2, "[OK]", f"Process exited ({elapsed:.1f}s)")
        print("\n[OK] Project process ended")


def clean(config: ProjectConfig) -> None:
    if not run_task(config, "clean"):
        raise IceywingError("No clean task. Iceywing refuses to guess which generated files are safe.")


def reset(config: ProjectConfig) -> None:
    clean(config)
    up(config)


def verify(config: ProjectConfig, *, quiet: bool = False) -> VerifyResult:
    """Run the project-owned verifier and return a parsed presentation summary.

    The project command remains authoritative: Iceywing only captures, parses, and
    summarizes its output. Direct `just verify` behavior is never modified.
    """
    task = _task(config, "verify")
    if task:
        if not quiet and not is_quiet():
            print("->", " ".join(task))
        return run_verification(
            task,
            cwd=config.root,
            label="Verification",
            log_prefix="verify",
            heartbeat=not quiet,
        )

    package_json = config.root / "package.json"
    if package_json.exists() and command_exists("npm"):
        data = json.loads(package_json.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
        candidates = ["lint", "typecheck", "test", "build"]
        selected = [name for name in candidates if name in scripts]
        if selected:
            results: list[VerifyResult] = []
            total = len(selected)
            for index, name in enumerate(selected, 1):
                if not quiet:
                    progress(index, total, "[....]", name)
                cmd = ["npm", "test"] if name == "test" else ["npm", "run", name]
                result = run_verification(
                    cmd,
                    cwd=config.root,
                    label=f"Verification: {name}",
                    log_prefix=f"verify-{name}",
                    heartbeat=not quiet,
                )
                results.append(result)
                if not quiet:
                    progress(index, total, "[OK]", name)
            return merge_results(results)

    raise IceywingError("No verify task. Define `just verify` or [tasks].verify.")
