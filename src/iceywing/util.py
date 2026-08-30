from __future__ import annotations

import fnmatch
import hashlib
import locale
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .runtime import identify, terminate_tree


class IceywingError(RuntimeError):
    pass


_OUTPUT_MODE = "normal"


def configure_output(*, verbose: bool = False, quiet: bool = False) -> None:
    global _OUTPUT_MODE
    if verbose and quiet:
        raise IceywingError("Use either --verbose or --quiet, not both.")
    _OUTPUT_MODE = "verbose" if verbose else "quiet" if quiet else "normal"


def output_mode() -> str:
    return _OUTPUT_MODE


def is_verbose() -> bool:
    return _OUTPUT_MODE == "verbose"


def is_quiet() -> bool:
    return _OUTPUT_MODE == "quiet"


def say(message: str = "") -> None:
    if not is_quiet():
        print(message)


def prepare_command(args: Sequence[str]) -> list[str]:
    command = list(args)
    if not command:
        raise IceywingError("Cannot run an empty command.")

    if os.name != "nt":
        return command

    executable = shutil.which(command[0]) or command[0]
    suffix = Path(executable).suffix.lower()
    if suffix in {".cmd", ".bat"}:
        comspec = os.environ.get("ComSpec") or os.environ.get("COMSPEC") or "cmd.exe"
        command_line = subprocess.list2cmdline([executable, *command[1:]])
        return [comspec, "/d", "/s", "/c", command_line]

    command[0] = executable
    return command


def _child_env() -> dict[str, str]:
    child_env = os.environ.copy()
    child_env.setdefault("NO_COLOR", "1")
    child_env.setdefault("CLICOLOR", "0")
    child_env.setdefault("FORCE_COLOR", "0")
    return child_env


def _decode_output(raw: bytes | None) -> str | None:
    if raw is None:
        return None

    encodings = ["utf-8-sig", locale.getpreferredencoding(False)]
    seen: set[str] = set()
    for encoding in encodings:
        key = encoding.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    return raw.decode("utf-8", errors="replace")


def run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    prepared = prepare_command(args)
    if capture:
        completed = subprocess.run(
            prepared,
            cwd=str(cwd) if cwd else None,
            text=False,
            capture_output=True,
            env=_child_env(),
        )
        result = subprocess.CompletedProcess(
            completed.args,
            completed.returncode,
            _decode_output(completed.stdout),
            _decode_output(completed.stderr),
        )
    else:
        completed = subprocess.run(
            prepared,
            cwd=str(cwd) if cwd else None,
            text=False,
            capture_output=False,
            env=_child_env(),
        )
        result = subprocess.CompletedProcess(completed.args, completed.returncode, None, None)

    if check and result.returncode != 0:
        stderr = result.stderr or ""
        stdout = result.stdout or ""
        message = stderr.strip() or stdout.strip() or f"command exited with code {result.returncode}"
        raise IceywingError(f"$ {' '.join(args)}\n{message}")
    return result


def _log_path(prefix: str) -> Path:
    log_dir = state_home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in prefix).strip("-") or "task"
    return log_dir / f"{stamp}-{safe}.log"


def _failure_message(
    *,
    args: Sequence[str],
    label: str,
    returncode: int,
    output: str,
    log_path: Path,
    tail_lines: int,
) -> str:
    lines = output.rstrip().splitlines()
    tail = "\n".join(lines[-tail_lines:]) if lines else "(no command output)"
    return (
        f"Failed while: {label}\n"
        f"Command: {' '.join(args)}\n"
        f"Exit code: {returncode}\n\n"
        f"Last output:\n{tail}\n\n"
        f"Full log: {log_path}"
    )


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    identity = identify(process.pid)
    terminate_tree(
        process.pid,
        create_time=identity.create_time if identity else None,
        timeout=3.0,
    )


def run_logged(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    label: str,
    log_prefix: str = "task",
    tail_lines: int = 24,
    heartbeat: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a finite task, keep a full log, and show details only when useful."""
    if is_verbose():
        started = time.monotonic()
        result = run(args, cwd=cwd, capture=False, check=False)
        elapsed = time.monotonic() - started
        if result.returncode != 0:
            raise IceywingError(
                f"Failed while: {label}\nCommand: {' '.join(args)}\nExit code: {result.returncode}"
            )
        result.iceywing_elapsed = elapsed  # type: ignore[attr-defined]
        return result

    prepared = prepare_command(args)
    log_path = _log_path(log_prefix)
    started = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    try:
        with log_path.open("wb") as stream:
            process = subprocess.Popen(
                prepared,
                cwd=str(cwd) if cwd else None,
                stdout=stream,
                stderr=subprocess.STDOUT,
                env=_child_env(),
            )
            next_report = 3.0
            while True:
                returncode = process.poll()
                elapsed = time.monotonic() - started
                if returncode is not None:
                    break
                tick_progress()
                if heartbeat and not is_quiet() and not live_progress_active() and elapsed >= next_report:
                    print(f"      -> {label} ({elapsed:.0f}s)", flush=True)
                    next_report += 15.0
                time.sleep(0.2)
    except KeyboardInterrupt:
        if process is not None:
            _terminate_process_tree(process)
        raise

    raw = log_path.read_bytes() if log_path.exists() else b""
    output = _decode_output(raw) or ""
    result = subprocess.CompletedProcess(prepared, returncode, output, None)
    elapsed = time.monotonic() - started

    if result.returncode != 0:
        raise IceywingError(
            _failure_message(
                args=args,
                label=label,
                returncode=result.returncode,
                output=output,
                log_path=log_path,
                tail_lines=tail_lines,
            )
        )

    result.iceywing_log = str(log_path)  # type: ignore[attr-defined]
    result.iceywing_elapsed = elapsed  # type: ignore[attr-defined]
    return result


def run_live_logged(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    label: str,
    log_prefix: str = "run",
    tail_lines: int = 30,
    on_line: Callable[[str], bool | None] | None = None,
    on_start: Callable[[subprocess.Popen[bytes]], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a long-lived process, tee to a log, and optionally summarize live lines."""
    prepared = prepare_command(args)
    log_path = _log_path(log_prefix)
    started = time.monotonic()
    process = subprocess.Popen(
        prepared,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=_child_env(),
    )
    if process.stdout is None:
        raise IceywingError(f"Failed while: {label}\nCould not capture process output.")
    if on_start is not None:
        on_start(process)

    q: queue.Queue[bytes | None] = queue.Queue()

    def reader() -> None:
        try:
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                q.put(line)
        finally:
            q.put(None)

    thread = threading.Thread(target=reader, name="iceywing-output", daemon=True)
    thread.start()
    reader_done = False
    ready = False
    next_report = 3.0

    try:
        with log_path.open("wb") as stream:
            while True:
                try:
                    raw = q.get(timeout=0.2)
                except queue.Empty:
                    raw = b""

                if raw is None:
                    reader_done = True
                elif raw:
                    stream.write(raw)
                    stream.flush()
                    text = _decode_output(raw) or ""
                    if is_verbose():
                        print(text, end="" if text.endswith("\n") else "\n", flush=True)
                    elif not is_quiet() and on_line is not None:
                        ready = bool(on_line(text.rstrip("\r\n"))) or ready

                elapsed = time.monotonic() - started
                tick_progress()
                if (
                    not ready
                    and not is_verbose()
                    and not is_quiet()
                    and not live_progress_active()
                    and elapsed >= next_report
                ):
                    print(f"      -> {label} ({elapsed:.0f}s)", flush=True)
                    next_report += 15.0

                returncode = process.poll()
                if returncode is not None and reader_done and q.empty():
                    break
    except KeyboardInterrupt:
        _terminate_process_tree(process)
        raise

    thread.join(timeout=1)
    raw_output = log_path.read_bytes() if log_path.exists() else b""
    output = _decode_output(raw_output) or ""
    result = subprocess.CompletedProcess(prepared, process.returncode or 0, output, None)
    elapsed = time.monotonic() - started

    if result.returncode != 0:
        raise IceywingError(
            _failure_message(
                args=args,
                label=label,
                returncode=result.returncode,
                output=output,
                log_path=log_path,
                tail_lines=tail_lines,
            )
        )

    result.iceywing_log = str(log_path)  # type: ignore[attr-defined]
    result.iceywing_elapsed = elapsed  # type: ignore[attr-defined]
    return result


def shell_command(command: str) -> list[str]:
    if os.name == "nt":
        return ["powershell", "-NoProfile", "-Command", command]
    return ["sh", "-lc", command]


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def matches_any(value: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def confirm(prompt: str, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{prompt} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def confirm_required(prompt: str) -> bool:
    """Require explicit confirmation for destructive recovery operations."""
    if os.name == "nt":
        try:
            import msvcrt

            print(f"{prompt} [Y/N] (press one key) ", end="", flush=True)
            while True:
                key = msvcrt.getwch()
                if key == "\x03":
                    raise KeyboardInterrupt
                if key in {"\x00", "\xe0"}:
                    msvcrt.getwch()
                    continue
                lowered = key.lower()
                if lowered == "y":
                    print("Y")
                    return True
                if lowered == "n":
                    print("N")
                    return False
        except (ImportError, OSError):
            pass

    while True:
        answer = input(f"{prompt} [Y/N] ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter Y to confirm or N to cancel.")


def prompt_path(prompt: str) -> Path:
    raw = input(prompt).strip()
    if not raw:
        raise IceywingError("No file path provided.")
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        raw = raw[1:-1]
    return Path(raw).expanduser()


_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_PROGRESS_LOCK = threading.RLock()


class _LiveProgress:
    def __init__(self, index: int, total: int, label: str, width: int) -> None:
        self.index = index
        self.total = total
        self.label = label
        self.width = width
        self.started = time.monotonic()
        self.frame = 0
        self.last_length = 0
        self.stream = sys.stdout


_ACTIVE_PROGRESS: _LiveProgress | None = None


def _dynamic_progress_enabled() -> bool:
    if is_quiet() or is_verbose():
        return False
    preference = os.environ.get("ICEYWING_PROGRESS", "auto").strip().lower()
    if preference in {"plain", "off", "0", "false"}:
        return False
    if preference in {"dynamic", "on", "1", "true"}:
        return True
    if os.environ.get("CI") or os.environ.get("TERM", "").lower() == "dumb":
        return False
    try:
        return bool(sys.stdout.isatty())
    except (AttributeError, OSError):
        return False


def _enable_windows_vt() -> bool:
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if handle in {0, -1} or not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError, ValueError):
        return False


def _progress_color_enabled() -> bool:
    if "NO_COLOR" in os.environ or os.environ.get("CLICOLOR") == "0":
        return False
    return _enable_windows_vt()


def _render_dynamic_progress(
    state: _LiveProgress,
    status: str,
    *,
    elapsed: float | None,
) -> tuple[str, int]:
    filled = round(state.width * state.index / state.total)
    bar = "█" * filled + "░" * (state.width - filled)
    if status == "[....]":
        symbol = _SPINNER_FRAMES[state.frame % len(_SPINNER_FRAMES)]
        color = "36"
    elif status == "[OK]":
        symbol = "✓"
        color = "32"
    elif status == "[FAIL]":
        symbol = "✗"
        color = "31"
    elif status == "[WARN]":
        symbol = "!"
        color = "33"
    else:
        symbol = "•"
        color = "36"

    plain_symbol = symbol
    plain_bar = bar
    if _progress_color_enabled():
        symbol = f"\x1b[{color}m{symbol}\x1b[0m"
        bar = f"\x1b[{color}m{bar}\x1b[0m"

    duration = f"  {elapsed:5.1f}s" if elapsed is not None else ""
    plain = f"{plain_symbol} {state.label:<22} {plain_bar}  {state.index}/{state.total}{duration}"
    styled = f"{symbol} {state.label:<22} {bar}  {state.index}/{state.total}{duration}"
    return styled, len(plain)


def _draw_active_progress(state: _LiveProgress, status: str = "[....]") -> None:
    elapsed = time.monotonic() - state.started
    text, visible_length = _render_dynamic_progress(state, status, elapsed=elapsed)
    if _progress_color_enabled():
        state.stream.write("\r\x1b[2K" + text)
    else:
        padding = " " * max(0, state.last_length - visible_length)
        state.stream.write("\r" + text + padding)
    state.stream.flush()
    state.last_length = visible_length


def live_progress_active() -> bool:
    with _PROGRESS_LOCK:
        return _ACTIVE_PROGRESS is not None


def tick_progress() -> None:
    with _PROGRESS_LOCK:
        if _ACTIVE_PROGRESS is None:
            return
        _ACTIVE_PROGRESS.frame += 1
        _draw_active_progress(_ACTIVE_PROGRESS)


def progress_note(message: str) -> None:
    """Print a durable note without corrupting an active in-place progress row."""
    with _PROGRESS_LOCK:
        state = _ACTIVE_PROGRESS
        if state is None:
            print(message)
            return
        if _progress_color_enabled():
            state.stream.write("\r\x1b[2K")
        else:
            state.stream.write("\r" + " " * state.last_length + "\r")
        state.stream.write(message + ("" if message.endswith("\n") else "\n"))
        _draw_active_progress(state)


def abort_progress(status: str = "[FAIL]") -> None:
    global _ACTIVE_PROGRESS
    with _PROGRESS_LOCK:
        state = _ACTIVE_PROGRESS
        if state is None:
            return
        _draw_active_progress(state, status)
        state.stream.write("\n")
        state.stream.flush()
        _ACTIVE_PROGRESS = None


def progress(
    index: int,
    total: int,
    status: str,
    label: str,
    *,
    width: int = 12,
    live: bool = False,
) -> None:
    global _ACTIVE_PROGRESS
    if is_quiet():
        return
    total = max(1, total)
    index = min(max(index, 0), total)

    if live and _dynamic_progress_enabled():
        with _PROGRESS_LOCK:
            if status == "[....]":
                if _ACTIVE_PROGRESS is not None:
                    abort_progress("[WARN]")
                _ACTIVE_PROGRESS = _LiveProgress(index, total, label, width)
                _draw_active_progress(_ACTIVE_PROGRESS)
                return

            if _ACTIVE_PROGRESS is not None:
                _ACTIVE_PROGRESS.index = index
                _ACTIVE_PROGRESS.total = total
                _ACTIVE_PROGRESS.label = label
                _ACTIVE_PROGRESS.width = width
                _draw_active_progress(_ACTIVE_PROGRESS, status)
                _ACTIVE_PROGRESS.stream.write("\n")
                _ACTIVE_PROGRESS.stream.flush()
                _ACTIVE_PROGRESS = None
                return

            state = _LiveProgress(index, total, label, width)
            text, _ = _render_dynamic_progress(state, status, elapsed=None)
            print(text)
            return

    filled = round(width * index / total)
    bar = "#" * filled + "-" * (width - filled)
    print(f"[{bar}] {index}/{total} {status:<6} {label}")



def concise_mark(status: str) -> str:
    """Use Unicode status marks interactively and durable ASCII marks elsewhere."""
    if _dynamic_progress_enabled():
        return {"ok": "✓", "fail": "✗", "warn": "!"}.get(status, "•")
    return {"ok": "[OK]", "fail": "[FAIL]", "warn": "[WARN]"}.get(status, "[--]")


def begin_activity(label: str) -> None:
    """Show transient spinner/progress only when an interactive terminal can redraw it."""
    if _dynamic_progress_enabled():
        progress(1, 1, "[....]", label, live=True)


def dismiss_activity() -> None:
    """Remove a transient progress row without leaving a duplicate completion line."""
    global _ACTIVE_PROGRESS
    with _PROGRESS_LOCK:
        state = _ACTIVE_PROGRESS
        if state is None:
            return
        if _progress_color_enabled():
            state.stream.write("\r\x1b[2K")
        else:
            state.stream.write("\r" + " " * state.last_length + "\r")
        state.stream.flush()
        _ACTIVE_PROGRESS = None

def state_home() -> Path:
    override = os.environ.get("ICEYWING_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Iceywing"
    xdg = os.environ.get("XDG_STATE_HOME")
    return Path(xdg) / "iceywing" if xdg else Path.home() / ".local" / "state" / "iceywing"
