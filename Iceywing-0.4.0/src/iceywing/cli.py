from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from . import environment, popflow, release
from .init_project import init
from .project import current_project
from .selftest import self_test
from .util import IceywingError, abort_progress, configure_output, prompt_path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="iceywing",
        description="* Iceywing - Environment + Pop Flow",
    )
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-v", "--verbose", action="store_true", help="Show underlying command output.")
    p.add_argument("-q", "--quiet", action="store_true", help="Show only final results and errors.")

    sub = p.add_subparsers(dest="section")

    init_p = sub.add_parser("init", help="Create iceywing.toml and starter justfile.")
    init_p.add_argument("--force", action="store_true")

    doctor_p = sub.add_parser("doctor", help="Environment health check.")
    doctor_p.add_argument("path", type=Path, nargs="?")

    up_p = sub.add_parser("up", help="Ensure a project environment is ready.")
    up_p.add_argument("path", type=Path, nargs="?")
    up_p.add_argument("--fresh", action="store_true", help="Force a full setup.")
    up_p.add_argument("--repair", action="store_true", help="Repair only if health checks fail.")

    run_p = sub.add_parser("run", help="Run the configured project with concise live status.")
    run_p.add_argument("path", type=Path, nargs="?")
    run_p.add_argument("--replace", action="store_true", help="Replace an existing Iceywing-tracked run.")

    stop_p = sub.add_parser("stop", help="Stop the Iceywing-tracked project process tree.")
    stop_p.add_argument("path", type=Path, nargs="?")

    self_test_p = sub.add_parser("self-test", help="Run fast isolated Iceywing checks.")
    self_test_p.add_argument("--full", action="store_true", help="Include local push and full process-tree checks.")
    self_test_p.add_argument("--list", action="store_true", dest="list_only", help="List available checks.")
    self_test_p.add_argument("--only", action="append", metavar="CHECK", help="Run one check; may be repeated.")
    self_test_p.add_argument("--json", action="store_true", dest="json_output", help="Emit machine-readable JSON.")
    self_test_p.add_argument("--keep-temp", action="store_true", help="Keep isolated test artifacts for debugging.")

    release_p = sub.add_parser("release", help="Build and publish GitHub releases without requiring gh.")
    release_s = release_p.add_subparsers(dest="release_cmd", required=True)
    publish_p = release_s.add_parser("publish", help="Publish the current version as a GitHub Release.")
    publish_p.add_argument("--dry-run", action="store_true", help="Show the release plan without Git or GitHub writes.")
    publish_p.add_argument("--commit", action="store_true", help="Explicitly commit current working-tree changes as the release commit.")
    preview_p = release_s.add_parser("preview", help=argparse.SUPPRESS)
    preview_p.add_argument("--dry-run", action="store_true")
    preview_p.add_argument("--commit", action="store_true")

    env = sub.add_parser("env", help="Project environment.")
    envs = env.add_subparsers(dest="env_cmd", required=True)
    for name in ["doctor", "up", "run", "stop", "clean", "reset"]:
        envs.add_parser(name)

    pop = sub.add_parser("pop", help="Patch / Operation / Push Flow.")
    pops = pop.add_subparsers(dest="pop_cmd", required=True)
    pops.add_parser("status")
    pops.add_parser("verify")
    pops.add_parser("baseline")
    pops.add_parser("diff")
    pops.add_parser("undo")
    pops.add_parser("resume")

    inspect_p = pops.add_parser("inspect")
    inspect_p.add_argument("patch", type=Path, nargs="?")

    apply_p = pops.add_parser("apply")
    apply_p.add_argument("patch", type=Path, nargs="?")
    apply_p.add_argument("--force", action="store_true")
    apply_p.add_argument("--3way", dest="three_way", action="store_true")
    apply_p.add_argument("--no-verify", action="store_true")
    apply_p.add_argument("--skip-baseline", action="store_true")
    apply_p.add_argument("--commit", action="store_true", help=argparse.SUPPRESS)

    commit_p = pops.add_parser("commit")
    commit_p.add_argument("-m", "--message")

    push_p = pops.add_parser("push")
    push_p.add_argument("--dry-run", action="store_true", help="Check the remote push without updating it.")
    push_p.add_argument("-y", "--yes", action="store_true", help=argparse.SUPPRESS)

    hist_p = pops.add_parser("history")
    hist_p.add_argument("--limit", type=int, default=20)

    return p


def _extract_output_flags(argv: list[str]) -> tuple[list[str], bool, bool]:
    verbose = False
    quiet = False
    filtered: list[str] = []
    for token in argv:
        if token in {"-v", "--verbose"}:
            verbose = True
            continue
        if token in {"-q", "--quiet"}:
            quiet = True
            continue
        filtered.append(token)
    return filtered, verbose, quiet


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    filtered, verbose, quiet = _extract_output_flags(raw)

    try:
        configure_output(verbose=verbose, quiet=quiet)
        p = parser()
        args = p.parse_args(filtered)

        if args.section == "init":
            init(Path.cwd(), force=args.force)
            return 0

        if args.section == "self-test":
            self_test(
                full=args.full,
                only=args.only,
                list_only=args.list_only,
                json_output=args.json_output,
                keep_temp=args.keep_temp,
            )
            return 0

        if args.section == "release":
            config = current_project()
            if args.release_cmd in {"publish", "preview"}:
                release.publish(config, dry_run=args.dry_run, commit=args.commit)
            return 0

        project_path = getattr(args, "path", None) if args.section in {"doctor", "up", "run", "stop"} else None
        config = current_project(project_path)

        if args.section is None:
            popflow.status(config)
            return 0

        if args.section == "doctor":
            return 0 if environment.doctor(config) else 1

        if args.section == "up":
            environment.up(config, fresh=args.fresh, repair=args.repair)
            return 0

        if args.section == "run":
            environment.run_project(config, replace=args.replace)
            return 0

        if args.section == "stop":
            environment.stop_project(config)
            return 0

        if args.section == "env":
            mapping = {
                "doctor": environment.doctor,
                "up": environment.up,
                "run": environment.run_project,
                "stop": environment.stop_project,
                "clean": environment.clean,
                "reset": environment.reset,
            }
            result = mapping[args.env_cmd](config)
            if args.env_cmd == "doctor":
                return 0 if result else 1
            return 0

        if args.section == "pop":
            if args.pop_cmd == "status":
                popflow.status(config)
            elif args.pop_cmd == "inspect":
                patch = args.patch or prompt_path("Drop .patch/.icepatch here, then press Enter: ")
                popflow.inspect(config, patch)
            elif args.pop_cmd == "verify":
                popflow.verify(config)
            elif args.pop_cmd == "baseline":
                popflow.baseline(config)
            elif args.pop_cmd == "diff":
                popflow.diff(config)
            elif args.pop_cmd == "apply":
                patch = args.patch or prompt_path("Drop .patch/.icepatch here, then press Enter: ")
                popflow.apply(
                    config,
                    patch,
                    force=args.force,
                    three_way=args.three_way,
                    no_verify=args.no_verify,
                    skip_baseline=args.skip_baseline,
                    commit_now=args.commit,
                )
            elif args.pop_cmd == "commit":
                popflow.commit(config, args.message)
            elif args.pop_cmd == "push":
                popflow.push(config, dry_run=args.dry_run, yes=args.yes)
            elif args.pop_cmd == "history":
                popflow.history(config, args.limit)
            elif args.pop_cmd == "undo":
                popflow.undo(config)
            elif args.pop_cmd == "resume":
                popflow.resume(config)
            return 0

        p.print_help()
        return 0

    except IceywingError as exc:
        abort_progress("[FAIL]")
        print(f"\nIceywing error:\n{exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        abort_progress("[WARN]")
        print("\nCancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
