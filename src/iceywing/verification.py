from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Sequence

from .util import (
    IceywingError,
    _child_env,
    _decode_output,
    _log_path,
    _terminate_process_tree,
    is_quiet,
    is_verbose,
    prepare_command,
    tick_progress,
    concise_mark,
)


_VITEST_FILES = re.compile(r"^\s*Test Files\s+(\d+)\s+passed\b", re.IGNORECASE | re.MULTILINE)
_VITEST_TESTS = re.compile(r"^\s*Tests\s+(\d+)\s+passed\b", re.IGNORECASE | re.MULTILINE)
_VITEST_FILE_FALLBACK = re.compile(r"^[\s✓✔]+\S.*?\((\d+)\s+tests?\)", re.IGNORECASE | re.MULTILINE)
_VITE_BUILD = re.compile(r"(?:✓|✔)\s+built in\s+[\d.]+(?:ms|s)\b", re.IGNORECASE)
_VITE_LARGE_CHUNK = re.compile(r"Some chunks are larger than\s+\d+\s*kB", re.IGNORECASE)
_WARNING_LINE = re.compile(r"(?:\bwarning\b|\[warn(?:ing)?\]|⚠)", re.IGNORECASE)
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@dataclass(frozen=True)
class VerifyResult:
    passed: bool
    duration_s: float
    log_path: Path
    returncode: int = 0
    test_files: int | None = None
    tests: int | None = None
    build_ok: bool | None = None
    warnings: int = 0
    failed_stage: str | None = None
    excerpt: str | None = None
    recognized: bool = False
    json_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["log_path"] = str(self.log_path)
        data["json_path"] = str(self.json_path) if self.json_path else None
        return data


class VerificationFailed(IceywingError):
    def __init__(self, result: VerifyResult) -> None:
        self.result = result
        super().__init__(format_failure(result, mark=concise_mark("fail")))


def _clean(text: str) -> str:
    return _ANSI.sub("", text).replace("\r", "")


def _sum_matches(pattern: re.Pattern[str], text: str) -> int | None:
    values = [int(value) for value in pattern.findall(text)]
    return sum(values) if values else None


def _warning_count(text: str) -> int:
    categories: set[str] = set()
    if _VITE_LARGE_CHUNK.search(text):
        categories.add("vite.large-chunk")

    for raw in text.splitlines():
        line = raw.strip()
        if not line or not _WARNING_LINE.search(line):
            continue
        lowered = line.lower()
        if "some chunks are larger than" in lowered:
            continue
        if re.search(r"\b0\s+warnings?\b", lowered):
            continue
        # Collapse volatile numbers/paths so a multi-line repeated warning counts once.
        normalized = re.sub(r"\d+(?:\.\d+)?", "#", lowered)
        normalized = re.sub(r"[a-z]:[/\\][^\s]+|/(?:[^\s/]+/)+[^\s]+", "<path>", normalized)
        categories.add(normalized[:180])
    return len(categories)


def _failure_stage(text: str) -> str:
    lowered = text.lower()
    if (
        re.search(r"\berror\s+ts\d+\b", lowered)
        or "tsc --" in lowered
        or "typescript" in lowered
        or "typecheck" in lowered
    ):
        return "typecheck"
    if "vitest" in lowered or re.search(r"^\s*fail\b", text, re.IGNORECASE | re.MULTILINE):
        return "test"
    if "eslint" in lowered or "lint error" in lowered:
        return "lint"
    if "vite" in lowered or "build failed" in lowered or "error during build" in lowered:
        return "build"
    return "verify"


def _error_index(lines: list[str]) -> int:
    scored: list[tuple[int, int]] = []
    patterns = [
        (100, re.compile(r"\berror\s+TS\d+\b", re.IGNORECASE)),
        (95, re.compile(r"^\s*FAIL\b", re.IGNORECASE)),
        (90, re.compile(r"AssertionError|Unhandled Error|Error:\s", re.IGNORECASE)),
        (85, re.compile(r"expected:|received:", re.IGNORECASE)),
        (75, re.compile(r"\bfailed\b|\bfailure\b", re.IGNORECASE)),
        (60, re.compile(r"\berror\b", re.IGNORECASE)),
    ]
    for index, line in enumerate(lines):
        for score, pattern in patterns:
            if pattern.search(line):
                scored.append((score, index))
                break
    if not scored:
        return max(0, len(lines) - 10)
    best_score = max(score for score, _ in scored)
    return next(index for score, index in scored if score == best_score)


def _excerpt(text: str, *, max_lines: int = 13) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    if not lines:
        return "(no command output)"
    center = _error_index(lines)
    start = max(0, center - 3)
    end = min(len(lines), start + max_lines)
    if end - start < max_lines:
        start = max(0, end - max_lines)
    selected = lines[start:end]
    while selected and not selected[0].strip():
        selected.pop(0)
    while selected and not selected[-1].strip():
        selected.pop()
    return "\n".join(selected) or "(no command output)"


def parse_output(
    output: str,
    *,
    passed: bool,
    duration_s: float,
    log_path: Path,
    returncode: int = 0,
) -> VerifyResult:
    text = _clean(output)
    test_files = _sum_matches(_VITEST_FILES, text)
    tests = _sum_matches(_VITEST_TESTS, text)

    # Some runners omit the Vitest aggregate line. Only use per-file counts as a fallback.
    if test_files is None:
        detail_counts = _VITEST_FILE_FALLBACK.findall(text)
        if detail_counts:
            test_files = len(detail_counts)
            if tests is None:
                tests = sum(int(value) for value in detail_counts)

    build_ok = True if _VITE_BUILD.search(text) else None
    warnings = _warning_count(text)
    recognized = any(value is not None for value in (test_files, tests, build_ok)) or warnings > 0

    return VerifyResult(
        passed=passed,
        duration_s=duration_s,
        log_path=log_path,
        returncode=returncode,
        test_files=test_files,
        tests=tests,
        build_ok=build_ok,
        warnings=warnings,
        failed_stage=None if passed else _failure_stage(text),
        excerpt=None if passed else _excerpt(text),
        recognized=recognized,
    )


def _write_json(result: VerifyResult) -> VerifyResult:
    path = result.log_path.with_suffix(".json")
    result = replace(result, json_path=path)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(result.to_dict(), stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return result


def run_verification(
    args: Sequence[str],
    *,
    cwd: Path,
    label: str = "Verification",
    log_prefix: str = "verify",
    heartbeat: bool = False,
) -> VerifyResult:
    """Run the project's verifier without changing its behavior, preserving full output in a log."""
    prepared = prepare_command(args)
    log_path = _log_path(log_prefix)
    started = time.monotonic()
    process: subprocess.Popen[bytes] | None = None

    try:
        if is_verbose():
            process = subprocess.Popen(
                prepared,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=_child_env(),
            )
            if process.stdout is None:
                raise IceywingError(f"Failed while: {label}\nCould not capture verifier output.")
            with log_path.open("wb") as stream:
                while True:
                    raw = process.stdout.readline()
                    if raw:
                        stream.write(raw)
                        stream.flush()
                        text = _decode_output(raw) or ""
                        print(text, end="" if text.endswith("\n") else "\n", flush=True)
                    elif process.poll() is not None:
                        break
        else:
            with log_path.open("wb") as stream:
                process = subprocess.Popen(
                    prepared,
                    cwd=str(cwd),
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    env=_child_env(),
                )
                next_report = 3.0
                while process.poll() is None:
                    elapsed = time.monotonic() - started
                    tick_progress()
                    if heartbeat and not is_quiet() and elapsed >= next_report:
                        # Keep non-interactive output concise: only long tasks receive a heartbeat.
                        print(f"      -> {label} ({elapsed:.0f}s)", flush=True)
                        next_report += 15.0
                    time.sleep(0.2)
    except KeyboardInterrupt:
        if process is not None:
            _terminate_process_tree(process)
        raise

    returncode = process.returncode if process is not None and process.returncode is not None else 1
    elapsed = time.monotonic() - started
    raw_output = log_path.read_bytes() if log_path.exists() else b""
    output = _decode_output(raw_output) or ""
    result = parse_output(
        output,
        passed=returncode == 0,
        duration_s=elapsed,
        log_path=log_path,
        returncode=returncode,
    )
    result = _write_json(result)

    if returncode != 0:
        raise VerificationFailed(result)
    return result


def merge_results(results: Sequence[VerifyResult]) -> VerifyResult:
    if not results:
        raise IceywingError("No verification results to merge.")
    return VerifyResult(
        passed=all(item.passed for item in results),
        duration_s=sum(item.duration_s for item in results),
        log_path=results[-1].log_path,
        returncode=0,
        test_files=sum(item.test_files or 0 for item in results) or None,
        tests=sum(item.tests or 0 for item in results) or None,
        build_ok=True if any(item.build_ok for item in results) else None,
        warnings=sum(item.warnings for item in results),
        recognized=any(item.recognized for item in results),
        json_path=results[-1].json_path,
    )


def format_summary(result: VerifyResult, *, mark: str = "✓") -> str:
    parts: list[str] = []
    if result.test_files is not None:
        parts.append(f"{result.test_files} files")
    if result.tests is not None:
        parts.append(f"{result.tests} tests")
    if result.build_ok:
        parts.append("build OK")
    if result.warnings:
        noun = "warning" if result.warnings == 1 else "warnings"
        parts.append(f"{result.warnings} {noun}")
    if not parts:
        parts.append("passed")
    parts.append(f"{result.duration_s:.1f}s")
    return f"{mark} Verify  " + " · ".join(parts)


def format_failure(result: VerifyResult, *, mark: str = "✗") -> str:
    stage = result.failed_stage or "verify"
    exit_part = f" · exit {result.returncode}" if result.returncode else ""
    lines = [f"{mark} Verify · {stage}{exit_part} · {result.duration_s:.1f}s", ""]
    if result.excerpt:
        lines.append(result.excerpt)
        lines.append("")
    lines.append(f"Log: {result.log_path}")
    return "\n".join(lines)
