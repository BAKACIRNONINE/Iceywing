from __future__ import annotations

from pathlib import Path

from . import environment
from .config import ProjectConfig
from .gitops import GitRepo
from .history import append, latest, new_id, operations
from .icepatch import load as load_package
from .safety import check_branch, patch_paths, sensitive_paths
from .verification import VerifyResult, format_summary
from .util import (
    IceywingError,
    begin_activity,
    concise_mark,
    dismiss_activity,
    confirm_required,
    is_quiet,
    is_verbose,
    progress as _render_progress,
    progress_note,
    tick_progress,
    run_logged,
    say,
)


def progress(index: int, total: int, status: str, label: str) -> None:
    """Use live terminal progress for Pop Flow while preserving plain log output."""
    _render_progress(index, total, status, label, live=True)


def status(config: ProjectConfig) -> None:
    print("* Iceywing\n")
    print(config.name)
    try:
        repo = GitRepo.discover(config.root)
        print(repo.branch())
        print()
        print(f"Environment  {'CONFIGURED' if (config.root / 'iceywing.toml').exists() else 'AUTO'}")
        print(f"Pop Flow     {'CLEAN' if repo.clean() else 'CHANGED'}")
    except IceywingError:
        print("(no Git repository)")
        print()
        print(f"Environment  {'CONFIGURED' if (config.root / 'iceywing.toml').exists() else 'AUTO'}")
        print("Pop Flow     UNAVAILABLE")


def inspect(config: ProjectConfig, path: Path) -> None:
    package = load_package(path)
    try:
        text = package.patch.read_text(encoding="utf-8", errors="replace")
        paths = patch_paths(text)
        sensitive = sensitive_paths(paths)
        print("* Pop Flow inspect\n")
        print(f"ID       {package.package_id}")
        print(f"SHA256   {package.sha256}")
        if package.project:
            print(f"Project  {package.project}")
        if package.branch:
            print(f"Branch   {package.branch}")
        if package.base_commit:
            print(f"Base     {package.base_commit}")
        if package.summary:
            print(f"Summary  {package.summary}")
        print(f"Files    {len(paths)}")
        for item in paths:
            print(f"  {item}")
        if sensitive:
            print("\n[WARN] Sensitive")
            for item in sensitive:
                print(f"  {item}")
    finally:
        package.close()


def _verify_summary_line(result: VerifyResult | None) -> str:
    mark = concise_mark("ok")
    if isinstance(result, VerifyResult):
        return format_summary(result, mark=mark)
    return f"{mark} Verify  passed"


def verify(config: ProjectConfig) -> None:
    print(f"* Verify · {config.name}\n")
    begin_activity("Verify project")
    try:
        result = environment.verify(config, quiet=True)
    except Exception:
        dismiss_activity()
        raise
    dismiss_activity()
    print(_verify_summary_line(result))


def baseline(config: ProjectConfig) -> None:
    repo = GitRepo.discover(config.root)
    if not repo.clean():
        raise IceywingError("Baseline verification requires a clean working tree.")
    print("* Pop Flow baseline\n")
    progress(1, 1, "[....]", "Verify baseline")
    try:
        environment.verify(config, quiet=True)
    except Exception:
        progress(1, 1, "[FAIL]", "Verify baseline")
        raise
    progress(1, 1, "[OK]", "Verify baseline")
    print("\n[OK] Baseline verification passed")


def diff(config: ProjectConfig) -> None:
    repo = GitRepo.discover(config.root)
    print("* Pop Flow diff\n")
    print(repo.diff_stat().strip() or "No working-tree diff.")
    names = repo.diff_names().strip()
    if names:
        print("\nFiles")
        print(names)


def _default_commit_message(package_id: str) -> str:
    clean = package_id.replace("_", "-").strip("-") or "change"
    return f"chore: apply {clean}"


def _status_summary(*, branch: str, files: int, verified: bool, commit_sha: str | None) -> None:
    if is_quiet():
        if commit_sha:
            print(f"[OK] committed {commit_sha[:12]}")
        return
    print("\n* Status Summary\n")
    print(f"Branch        {branch}")
    print(f"Files changed {files}")
    print("Apply         [OK]")
    print(f"Verify        {'[OK]' if verified else '[FAIL]'}")
    if commit_sha:
        print(f"Commit        [OK] {commit_sha[:12]}")
        print("Push          NOT DONE")
        print("\n[OK] Ready to push")
        print("Run: iceywing pop push")
    else:
        print("Commit        NOT DONE")


def apply(
    config: ProjectConfig,
    path: Path,
    *,
    force: bool = False,
    three_way: bool = False,
    no_verify: bool = False,
    skip_baseline: bool = False,
    commit_now: bool = False,
) -> None:
    del commit_now

    repo = GitRepo.discover(config.root)
    branch = repo.branch()
    before_head = repo.head()
    total_steps = 4 if not no_verify else 3

    say("* Iceywing Pop Flow\n")
    check_branch(config, branch, force=force)
    if not repo.clean():
        raise IceywingError("Working tree is not clean. Commit or stash existing changes before Pop Flow apply.")

    package = load_package(path)
    opid: str | None = None
    try:
        progress(1, total_steps, "[....]", "Preflight")

        if package.project and package.project != config.name and not force:
            raise IceywingError(f"Package project mismatch: expected '{package.project}', current '{config.name}'.")
        if package.branch and package.branch != branch and not force:
            raise IceywingError(f"Package branch mismatch: expected '{package.branch}', current '{branch}'.")
        if package.base_commit and not before_head.startswith(str(package.base_commit)) and not force:
            raise IceywingError(f"Base commit mismatch.\nExpected: {package.base_commit}\nCurrent:  {before_head}")

        text = package.patch.read_text(encoding="utf-8", errors="replace")
        paths = patch_paths(text)
        sensitive = sensitive_paths(paths)
        if sensitive and not is_quiet():
            progress_note("[WARN] Sensitive files: " + ", ".join(sensitive))

        if not no_verify and config.verify_baseline and not skip_baseline:
            if not is_quiet():
                progress_note("      -> Baseline verification")
            try:
                environment.verify(config, quiet=True)
            except Exception as exc:
                raise IceywingError(
                    "Baseline verification failed before the patch was applied. "
                    "The repository is unchanged.\n" + str(exc)
                ) from exc
        repo.apply_check(package.patch, three_way)
        progress(1, total_steps, "[OK]", "Preflight")

        progress(2, total_steps, "[....]", "Apply change")
        opid = new_id()
        repo.apply(package.patch, three_way)
        fingerprint = repo.diff_hash()
        delete_pref = (
            package.delete_after_success
            if package.delete_after_success is not None
            else config.delete_patch_after_success
        )
        commit_message = package.commit_message or _default_commit_message(package.package_id)
        append({
            "operation_id": opid,
            "event": "applied",
            "repo": str(repo.root),
            "project": config.name,
            "branch": branch,
            "before_head": before_head,
            "patch_id": package.package_id,
            "patch_sha256": package.sha256,
            "source_path": str(package.source),
            "delete_after_success": bool(delete_pref),
            "changed_files": paths,
            "post_diff_hash": fingerprint,
            "commit_message": commit_message,
            "verification_required": not no_verify,
        })
        progress(2, total_steps, "[OK]", "Apply change")

        verified = True
        next_step = 3
        if not no_verify:
            progress(3, total_steps, "[....]", "Verify project")
            try:
                verify_result = environment.verify(config, quiet=True)
                current_hash = repo.diff_hash()
                append({
                    "operation_id": opid,
                    "event": "verified",
                    "repo": str(repo.root),
                    "passed": True,
                    "post_diff_hash": current_hash,
                    "verification": verify_result.to_dict() if isinstance(verify_result, VerifyResult) else None,
                })
                progress(3, total_steps, "[OK]", "Verify project")
            except KeyboardInterrupt:
                append({
                    "operation_id": opid,
                    "event": "interrupted",
                    "repo": str(repo.root),
                    "stage": "verify",
                })
                progress(3, total_steps, "[WARN]", "Verify project")
                print("\n[WARN] Operation paused after apply.\nResume: iceywing pop resume")
                raise
            except Exception as exc:
                verified = False
                append({
                    "operation_id": opid,
                    "event": "verified",
                    "repo": str(repo.root),
                    "passed": False,
                    "error": str(exc),
                    "post_diff_hash": repo.diff_hash(),
                })
                progress(3, total_steps, "[FAIL]", "Verify project")
                print(f"\n{exc}")
                print("\nChange remains local. Fix the problem, then run: iceywing pop resume")
                _status_summary(branch=branch, files=len(paths), verified=False, commit_sha=None)
                return
            next_step = 4

        progress(next_step, total_steps, "[....]", "Commit change")
        try:
            sha = repo.commit(commit_message)
        except KeyboardInterrupt:
            append({
                "operation_id": opid,
                "event": "interrupted",
                "repo": str(repo.root),
                "stage": "commit",
            })
            progress(next_step, total_steps, "[WARN]", "Commit change")
            print("\n[WARN] Operation paused before commit completed.\nResume: iceywing pop resume")
            raise
        append({
            "operation_id": opid,
            "event": "committed",
            "repo": str(repo.root),
            "commit": sha,
            "commit_message": commit_message,
        })
        progress(next_step, total_steps, "[OK]", "Commit change")
        _status_summary(branch=branch, files=len(paths), verified=verified, commit_sha=sha)
        if not is_quiet():
            print(f"\nOperation {opid}")
    finally:
        package.close()


def commit(config: ProjectConfig, message: str | None) -> None:
    repo = GitRepo.discover(config.root)
    if repo.clean():
        raise IceywingError("No changes to commit.")
    item = latest(repo.root)
    if not message and item:
        message = item.get("commit_message")
    if not message:
        message = "chore: apply local change"
    sha = repo.commit(message)
    opid = item.get("operation_id") if item else new_id()
    append({"operation_id": opid, "event": "committed", "repo": str(repo.root), "commit": sha, "commit_message": message})
    print(f"[OK] Commit {sha[:12]}")


def resume(config: ProjectConfig) -> None:
    repo = GitRepo.discover(config.root)
    item = latest(repo.root)
    if not item:
        raise IceywingError("No Iceywing operation found to resume.")

    events = item["events"]
    event_names = {e.get("event") for e in events}
    patch_id = str(item.get("patch_id", "(manual)"))
    if "pushed" in event_names:
        print(f"{concise_mark('ok')} Latest operation is already pushed.")
        return
    if "committed" in event_names:
        print(f"* Resume · {patch_id}\n")
        print(f"{concise_mark('ok')} Commit  {str(item.get('commit', ''))[:12]}")
        print("\nNext: iceywing pop push")
        return
    if "applied" not in event_names:
        raise IceywingError("Latest operation has no applied change to resume.")
    if repo.clean():
        raise IceywingError("Working tree is clean; there is no local change to resume.")

    say(f"* Resume · {patch_id}\n")

    verification_required = bool(item.get("verification_required", True))
    verified_events = [e for e in events if e.get("event") == "verified"]
    last_verified = verified_events[-1] if verified_events else None
    expected_hash = item.get("post_diff_hash")
    checkpoint_valid = bool(
        verification_required
        and last_verified
        and last_verified.get("passed")
        and expected_hash
        and repo.diff_hash() == expected_hash
    )

    verify_result: VerifyResult | None = None
    verify_line: str
    if not verification_required:
        verify_line = f"{concise_mark('ok')} Verify  skipped"
    elif checkpoint_valid:
        # Verification checkpoint: reuse only when the working-tree fingerprint still matches.
        if is_verbose() and last_verified:
            verification_data = last_verified.get("verification")
            if isinstance(verification_data, dict):
                raw_log = verification_data.get("log_path")
                if raw_log:
                    path = Path(str(raw_log))
                    if path.exists():
                        text = path.read_text(encoding="utf-8", errors="replace")
                        print(text, end="" if text.endswith("\n") else "\n")
        verify_line = f"{concise_mark('ok')} Verify  checkpoint reused"
    else:
        begin_activity("Verify project")
        tick_progress()
        tick_progress()
        try:
            verify_result = environment.verify(config, quiet=True)
        except KeyboardInterrupt:
            dismiss_activity()
            append({
                "operation_id": item["operation_id"],
                "event": "interrupted",
                "repo": str(repo.root),
                "stage": "verify",
            })
            print("\n[WARN] Resume paused. Run `iceywing pop resume` again.")
            raise
        except Exception as exc:
            dismiss_activity()
            append({
                "operation_id": item["operation_id"],
                "event": "verified",
                "repo": str(repo.root),
                "passed": False,
                "error": str(exc),
                "post_diff_hash": repo.diff_hash(),
            })
            print(str(exc))
            return
        dismiss_activity()
        current_hash = repo.diff_hash()
        append({
            "operation_id": item["operation_id"],
            "event": "verified",
            "repo": str(repo.root),
            "passed": True,
            "post_diff_hash": current_hash,
            "verification": verify_result.to_dict() if isinstance(verify_result, VerifyResult) else None,
        })
        verify_line = _verify_summary_line(verify_result)

    message = item.get("commit_message") or f"chore: apply {item.get('patch_id', 'change')}"
    progress(2, 2, "[....]", "Commit change")
    tick_progress()
    try:
        sha = repo.commit(message)
    except Exception:
        progress(2, 2, "[FAIL]", "Commit change")
        raise
    progress(2, 2, "[OK]", "Commit change")
    append({
        "operation_id": item["operation_id"],
        "event": "committed",
        "repo": str(repo.root),
        "commit": sha,
        "commit_message": message,
    })

    print(verify_line)
    print(f"{concise_mark('ok')} Commit  {sha[:12]}")
    print("\nNext: iceywing pop push")


def push(config: ProjectConfig, *, dry_run: bool = False, yes: bool = False) -> None:
    del yes
    repo = GitRepo.discover(config.root)
    branch = repo.branch()
    head = repo.head()

    say("* Iceywing Push\n")
    progress(1, 2, "[....]", "Preflight")
    check_branch(config, branch)
    progress(1, 2, "[OK]", f"Preflight - {branch}")

    label = "Push dry run" if dry_run else "Push"
    progress(2, 2, "[....]", label)
    item = latest(repo.root)
    opid = item.get("operation_id") if item else new_id()
    args = ["git", "push"]
    if dry_run:
        args.append("--dry-run")
    try:
        run_logged(
            args,
            cwd=repo.root,
            label=f"{label} to origin",
            log_prefix="pop-push",
            heartbeat=True,
        )
    except Exception as exc:
        if not dry_run:
            append({
                "operation_id": opid,
                "event": "push_failed",
                "repo": str(repo.root),
                "commit": head,
                "error": str(exc),
            })
        progress(2, 2, "[FAIL]", label)
        raise

    progress(2, 2, "[OK]", label)

    if dry_run:
        print("\n[OK] Remote push check passed; nothing was changed.")
        return

    append({"operation_id": opid, "event": "pushed", "repo": str(repo.root), "commit": repo.head()})
    print(f"\n[OK] {branch} pushed to origin")

    item = latest(repo.root)
    source_path = Path(item.get("source_path", "")) if item and item.get("source_path") else None
    if item and item.get("delete_after_success") and source_path and source_path.exists():
        try:
            source_path.unlink()
            append({"operation_id": opid, "event": "source_deleted", "repo": str(repo.root)})
            if not is_quiet():
                print(f"[OK] Removed applied package: {source_path.name}")
        except OSError as exc:
            print(f"[WARN] Could not remove source package: {exc}")


def history(config: ProjectConfig, limit: int) -> None:
    repo = GitRepo.discover(config.root)
    rows = operations(repo.root)[:limit]
    if not rows:
        print("No Iceywing history for this repository.")
        return
    print("* Pop Flow history\n")
    for row in rows:
        event_names = {e.get("event") for e in row["events"]}
        if "pushed" in event_names:
            state = "PUSHED"
        elif "push_failed" in event_names:
            state = "PUSH_FAILED"
        elif "committed" in event_names:
            state = "COMMITTED"
        elif any(e.get("event") == "verified" and e.get("passed") for e in row["events"]):
            state = "PASS"
        elif any(e.get("event") == "verified" and not e.get("passed") for e in row["events"]):
            state = "FAIL"
        else:
            state = "APPLIED"
        print(f"{row['operation_id']:<12} {row.get('patch_id', '(manual)'):<36} {state}")


def undo(config: ProjectConfig) -> None:
    repo = GitRepo.discover(config.root)
    item = latest(repo.root)
    if not item:
        raise IceywingError("No Iceywing operation found.")
    event_names = {e.get("event") for e in item["events"]}
    opid = item["operation_id"]
    if "committed" in event_names:
        commit_sha = item.get("commit")
        if not commit_sha:
            raise IceywingError("Commit SHA missing from history.")
        print(f"Operation {opid} is committed as {commit_sha[:12]}.")
        if not confirm_required("Create a Git revert commit?"):
            print("Cancelled.")
            return
        repo.revert(commit_sha)
        append({"operation_id": opid, "event": "reverted", "repo": str(repo.root), "revert_head": repo.head()})
        print("[OK] Revert created")
        return
    expected = item.get("post_diff_hash")
    if not expected:
        raise IceywingError("No safe undo fingerprint recorded.")
    if repo.diff_hash() != expected:
        raise IceywingError("Working tree changed after the recorded operation. Automatic undo is blocked.")
    before = item.get("before_head")
    paths = item.get("changed_files", [])
    if not before:
        raise IceywingError("before_head missing.")
    if not confirm_required("Restore exact pre-operation state?"):
        print("Cancelled.")
        return
    repo.restore_pre_operation(before, paths)
    append({"operation_id": opid, "event": "undone", "repo": str(repo.root)})
    print("[OK] Operation undone")
