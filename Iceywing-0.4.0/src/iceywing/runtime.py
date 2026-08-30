from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    create_time: float


def identify(pid: int) -> ProcessIdentity | None:
    if pid <= 0:
        return None
    try:
        process = psutil.Process(pid)
        return ProcessIdentity(pid=pid, create_time=process.create_time())
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return None


def is_alive(pid: int, create_time: float | None = None) -> bool:
    try:
        process = psutil.Process(pid)
        if create_time is not None and abs(process.create_time() - create_time) > 0.01:
            return False
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False


def terminate_tree(
    pid: int,
    *,
    create_time: float | None = None,
    timeout: float = 5.0,
) -> list[int]:
    """Terminate a tracked process tree without relying on platform shell utilities.

    create_time protects against killing an unrelated process if the OS has reused a PID.
    Returns PIDs that required a final kill after the graceful wait.
    """
    try:
        root = psutil.Process(pid)
        if create_time is not None and abs(root.create_time() - create_time) > 0.01:
            return []
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return []

    try:
        children = root.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        children = []

    processes = [*reversed(children), root]
    for process in processes:
        try:
            process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    _, alive = psutil.wait_procs(processes, timeout=max(timeout, 0.1))
    forced: list[int] = []
    for process in alive:
        try:
            forced.append(process.pid)
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if alive:
        psutil.wait_procs(alive, timeout=2.0)
    return forced
