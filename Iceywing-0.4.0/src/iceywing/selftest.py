from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from . import __version__
from .runtime import identify, is_alive, terminate_tree
from .util import IceywingError, progress as _render_progress


def progress(index: int, total: int, status: str, label: str) -> None:
    """Keep self-test progress live in a terminal and durable when redirected."""
    _render_progress(index, total, status, label, live=True)


class _SelfTestContext:
    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="iceywing-self-test-"))
        self.state = self.root / "state"
        self.project = self.root / "project"
        self.remote = self.root / "remote.git"
        self.old_home = os.environ.get("ICEYWING_HOME")
        os.environ["ICEYWING_HOME"] = str(self.state)

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["ICEYWING_HOME"] = str(self.state)
        package_root = str(Path(__file__).resolve().parents[1])
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = package_root if not existing else package_root + os.pathsep + existing
        env.setdefault("NO_COLOR", "1")
        env.setdefault("CLICOLOR", "0")
        env.setdefault("FORCE_COLOR", "0")
        return env

    def restore_environment(self) -> None:
        if self.old_home is None:
            os.environ.pop("ICEYWING_HOME", None)
        else:
            os.environ["ICEYWING_HOME"] = self.old_home

    def cleanup(self) -> bool:
        self.restore_environment()
        for _ in range(20):
            try:
                shutil.rmtree(self.root)
                return True
            except FileNotFoundError:
                return True
            except (PermissionError, OSError):
                time.sleep(0.1)
        return False


def _tail(text: str, lines: int = 18) -> str:
    values = (text or "").rstrip().splitlines()
    return "\n".join(values[-lines:]) if values else "(no output)"


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 15,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise IceywingError(f"Command timed out after {timeout:.0f}s: {' '.join(args)}") from exc


def _require_success(result: subprocess.CompletedProcess[str], args: list[str]) -> None:
    if result.returncode == 0:
        return
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    raise IceywingError(
        f"Command failed ({result.returncode}): {' '.join(args)}\n{_tail(output)}"
    )


def _python_task(script: str) -> str:
    exe = str(Path(sys.executable).resolve())
    if os.name == "nt":
        return f'& "{exe}" "{script}"'
    import shlex

    return f"{shlex.quote(exe)} {shlex.quote(script)}"


def _write_fake_project(ctx: _SelfTestContext) -> None:
    ctx.project.mkdir(parents=True, exist_ok=True)
    (ctx.project / "setup.py").write_text(
        "from pathlib import Path\n"
        "p=Path('.setup-count')\n"
        "n=int(p.read_text() if p.exists() else '0')+1\n"
        "p.write_text(str(n))\n"
        "Path('.ready').write_text('ready')\n",
        encoding="utf-8",
    )
    (ctx.project / "doctor.py").write_text(
        "from pathlib import Path\n"
        "raise SystemExit(0 if Path('.ready').exists() else 1)\n",
        encoding="utf-8",
    )
    setup = _python_task("setup.py").replace("\\", "\\\\").replace('"', '\\"')
    doctor = _python_task("doctor.py").replace("\\", "\\\\").replace('"', '\\"')
    (ctx.project / "iceywing.toml").write_text(
        f'''[project]\nname = "Iceywing Self Test"\n\n[environment]\ntype = "generic"\n\n[tasks]\nsetup = "{setup}"\ndoctor = "{doctor}"\n\n[git]\nallowed_branches = ["research-v1"]\n''',
        encoding="utf-8",
    )


def _stage_cli(ctx: _SelfTestContext, *, full: bool) -> int:
    if sys.version_info < (3, 11):
        raise IceywingError(f"Python {sys.version.split()[0]} is unsupported; 3.11+ is required.")
    args = [sys.executable, "-m", "iceywing", "--version"]
    result = _run(args, env=ctx.env())
    _require_success(result, args)
    if result.stdout.strip() != __version__:
        raise IceywingError(
            f"python -m iceywing reports {result.stdout.strip()!r}; expected {__version__!r}."
        )
    return 2


def _stage_environment(ctx: _SelfTestContext, *, full: bool) -> int:
    _write_fake_project(ctx)
    probe = ctx.root / "filesystem-probe.txt"
    probe.write_text("iceywing\n", encoding="utf-8")
    if probe.read_text(encoding="utf-8") != "iceywing\n":
        raise IceywingError("Temporary filesystem read/write check failed.")

    args = [sys.executable, "-m", "iceywing", "up", str(ctx.project), "--quiet"]
    first = _run(args, env=ctx.env())
    _require_success(first, args)
    count = (ctx.project / ".setup-count").read_text(encoding="utf-8").strip()
    if count != "1":
        raise IceywingError(f"First environment setup ran {count} times; expected 1.")

    started = time.monotonic()
    second = _run(args, env=ctx.env())
    _require_success(second, args)
    elapsed = time.monotonic() - started
    count = (ctx.project / ".setup-count").read_text(encoding="utf-8").strip()
    if count != "1":
        raise IceywingError("Second `up` reran setup instead of using cached readiness.")
    if elapsed > 5:
        raise IceywingError(f"Cached environment check took {elapsed:.1f}s; expected under 5s.")
    return 4


def _git(ctx: _SelfTestContext, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = ["git", *args]
    result = _run(command, cwd=cwd or ctx.project, env=ctx.env())
    _require_success(result, command)
    return result


def _stage_git(ctx: _SelfTestContext, *, full: bool) -> int:
    if shutil.which("git") is None:
        raise IceywingError("Git is not available on PATH.")
    if not ctx.project.exists():
        _write_fake_project(ctx)

    _git(ctx, "init")
    _git(ctx, "config", "user.email", "iceywing-self-test@example.invalid")
    _git(ctx, "config", "user.name", "Iceywing Self Test")
    _git(ctx, "checkout", "-b", "research-v1")
    _git(ctx, "add", ".")
    _git(ctx, "commit", "-m", "self-test baseline")

    if not full:
        return 3

    _git(ctx, "init", "--bare", str(ctx.remote), cwd=ctx.root)
    _git(ctx, "remote", "add", "origin", str(ctx.remote))
    _git(ctx, "push", "-u", "origin", "research-v1")
    (ctx.project / "push-probe.txt").write_text("probe\n", encoding="utf-8")
    _git(ctx, "add", "push-probe.txt")
    _git(ctx, "commit", "-m", "self-test push")
    args = [sys.executable, "-m", "iceywing", "pop", "push", "--quiet"]
    result = _run(args, cwd=ctx.project, env=ctx.env())
    _require_success(result, args)
    local = _git(ctx, "rev-parse", "HEAD").stdout.strip()
    remote = _git(ctx, "--git-dir", str(ctx.remote), "rev-parse", "refs/heads/research-v1", cwd=ctx.root).stdout.strip()
    if local != remote:
        raise IceywingError("Local bare remote did not receive the pushed HEAD.")
    return 5


def _wait_for_file(path: Path, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.05)
    raise IceywingError(f"Timed out waiting for process fixture: {path.name}")


def _stage_process(ctx: _SelfTestContext, *, full: bool) -> int:
    ready = ctx.root / "process-ready.txt"
    child_pid_file = ctx.root / "child-pid.txt"

    if full:
        script = (
            "import pathlib, subprocess, sys, time; "
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            f"pathlib.Path({str(child_pid_file)!r}).write_text(str(child.pid)); "
            f"pathlib.Path({str(ready)!r}).write_text('ready'); "
            "time.sleep(60)"
        )
    else:
        script = (
            "import pathlib, time; "
            f"pathlib.Path({str(ready)!r}).write_text('ready'); "
            "time.sleep(60)"
        )

    process = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=str(ctx.root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    identity = identify(process.pid)
    if identity is None:
        process.kill()
        raise IceywingError("psutil could not identify the process fixture.")

    try:
        _wait_for_file(ready)
        if not is_alive(identity.pid, identity.create_time):
            raise IceywingError("Process fixture was not reported alive.")

        child_pid: int | None = None
        if full:
            _wait_for_file(child_pid_file)
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))
            if not is_alive(child_pid):
                raise IceywingError("Child process fixture was not reported alive.")

        terminate_tree(identity.pid, create_time=identity.create_time, timeout=2.0)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired as exc:
            raise IceywingError("Process tree did not stop within 3 seconds.") from exc

        if is_alive(identity.pid, identity.create_time):
            raise IceywingError("Tracked process remained alive after terminate_tree().")
        if child_pid is not None and is_alive(child_pid):
            raise IceywingError("Child process remained alive after terminate_tree().")
    finally:
        if process.poll() is None:
            terminate_tree(identity.pid, create_time=identity.create_time, timeout=1.0)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
    return 4 if full else 3


_STAGES: dict[str, tuple[str, Callable[[_SelfTestContext], int]]] = {}


def _stage_wrapper(func: Callable[..., int], full: bool) -> Callable[[_SelfTestContext], int]:
    return lambda ctx: func(ctx, full=full)


def available_checks() -> list[str]:
    return ["cli", "environment", "git", "process"]


def self_test(
    *,
    full: bool = False,
    only: list[str] | None = None,
    list_only: bool = False,
    json_output: bool = False,
    keep_temp: bool = False,
) -> dict[str, object]:
    names = available_checks()
    if list_only:
        if json_output:
            print(json.dumps({"checks": names}))
        else:
            for name in names:
                print(name)
        return {"checks": names}

    selected = only or names
    unknown = [name for name in selected if name not in names]
    if unknown:
        raise IceywingError(f"Unknown self-test check(s): {', '.join(unknown)}")

    label_map = {
        "cli": "CLI",
        "environment": "Environment",
        "git": "Git" if not full else "Git / push",
        "process": "Process" if not full else "Process tree",
    }
    function_map = {
        "cli": _stage_cli,
        "environment": _stage_environment,
        "git": _stage_git,
        "process": _stage_process,
    }

    started = time.monotonic()
    ctx = _SelfTestContext()
    checks = 0
    results: list[dict[str, object]] = []
    success = False
    retained_path: str | None = None
    if not json_output:
        print("* Iceywing Self Test\n")

    try:
        total = len(selected)
        for index, name in enumerate(selected, 1):
            label = label_map[name]
            if not json_output:
                progress(index, total, "[....]", label)
            stage_started = time.monotonic()
            try:
                count = function_map[name](ctx, full=full)
                checks += count
                elapsed = time.monotonic() - stage_started
                results.append({"name": name, "status": "ok", "duration_s": round(elapsed, 3)})
            except Exception as exc:
                elapsed = time.monotonic() - stage_started
                results.append(
                    {
                        "name": name,
                        "status": "fail",
                        "duration_s": round(elapsed, 3),
                        "error": str(exc),
                    }
                )
                retained_path = str(ctx.root)
                if not json_output:
                    progress(index, total, "[FAIL]", label)
                detail = str(exc) if isinstance(exc, IceywingError) else f"{type(exc).__name__}: {exc}"
                raise IceywingError(
                    f"Self-test failed at {label}.\n{detail}\nArtifacts retained: {ctx.root}"
                ) from exc
            if not json_output:
                progress(index, total, "[OK]", label)

        success = True
    finally:
        ctx.restore_environment()
        if success:
            if keep_temp:
                retained_path = str(ctx.root)
            else:
                cleaned = ctx.cleanup()
                if not cleaned:
                    retained_path = str(ctx.root)

    elapsed = time.monotonic() - started
    payload: dict[str, object] = {
        "status": "ok" if success else "fail",
        "mode": "full" if full else "smoke",
        "checks_passed": checks,
        "duration_s": round(elapsed, 3),
        "results": results,
        "temp_retained": retained_path is not None,
        "temp_path": retained_path,
    }
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"\n[OK] {checks} checks passed in {elapsed:.1f}s")
        if retained_path:
            reason = "requested" if keep_temp else "cleanup deferred by Windows"
            print(f"[WARN] Temporary artifacts retained ({reason}): {retained_path}")
    return payload
