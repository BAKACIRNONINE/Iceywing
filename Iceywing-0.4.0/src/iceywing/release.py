from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import environment
from .config import ProjectConfig
from .gitops import GitRepo
from .util import IceywingError, concise_mark, run, run_logged
from .verification import format_summary

_GITHUB_API = "https://api.github.com"
_GITHUB_UPLOADS = "https://uploads.github.com"
_REMOTE_HTTPS = re.compile(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
_REMOTE_SCP = re.compile(r"^(?:[^@]+@)?github\.com:([^/]+)/([^/]+?)(?:\.git)?$")
_REMOTE_SSH = re.compile(r"^ssh://(?:[^@]+@)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
_ALPHA_VERSION = re.compile(r"^(?P<base>\d+\.\d+(?:\.\d+)?)a(?P<preview>\d+)$")


@dataclass(frozen=True)
class ReleaseIdentity:
    project_name: str
    package_version: str
    display_version: str
    preview_number: int | None
    tag: str
    title: str
    archive_name: str
    notes_path: Path | None


@dataclass(frozen=True)
class ReleaseArtifacts:
    source_zip: Path
    wheel: Path


def _project_metadata(root: Path) -> tuple[str, str]:
    path = root / "pyproject.toml"
    if not path.exists():
        raise IceywingError("Release requires pyproject.toml with [project].name and version.")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise IceywingError(f"Could not read pyproject.toml: {exc}") from exc
    project = data.get("project", {})
    name = str(project.get("name", "")).strip()
    version = str(project.get("version", "")).strip()
    if not name or not version:
        raise IceywingError("pyproject.toml must define [project].name and version for release.")
    return name, version


def _release_identity(root: Path) -> ReleaseIdentity:
    name, version = _project_metadata(root)
    display_name = name[:1].upper() + name[1:] if name.islower() else name
    match = _ALPHA_VERSION.fullmatch(version)
    preview_number: int | None = None
    display_version = version
    title = f"{display_name} {version}"
    archive_name = f"{display_name}-{version}.zip"
    notes_path: Path | None = None

    if match:
        base = match.group("base")
        preview_number = int(match.group("preview"))
        short_base = base[:-2] if base.endswith(".0") else base
        display_version = f"{short_base} Preview{preview_number}"
        title = f"{display_name} {display_version}"
        archive_name = f"{display_name}-{short_base}-preview{preview_number}.zip"
        candidate = root / "docs" / f"RELEASE_NOTES_{short_base}-preview{preview_number}.md"
        if candidate.exists():
            notes_path = candidate
    else:
        candidate = root / "docs" / f"RELEASE_NOTES_{version}.md"
        if candidate.exists():
            notes_path = candidate

    return ReleaseIdentity(
        project_name=name,
        package_version=version,
        display_version=display_version,
        preview_number=preview_number,
        tag=f"v{version}",
        title=title,
        archive_name=archive_name,
        notes_path=notes_path,
    )


def _origin_repo(root: Path) -> str:
    result = run(["git", "config", "--get", "remote.origin.url"], cwd=root, check=False)
    remote = (result.stdout or "").strip()
    if not remote:
        raise IceywingError("Git remote 'origin' is not configured.")
    for pattern in (_REMOTE_HTTPS, _REMOTE_SCP, _REMOTE_SSH):
        match = pattern.fullmatch(remote)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    raise IceywingError(
        "Built-in release currently supports GitHub origin remotes only.\n"
        f"Origin: {remote}"
    )


def _credential_token() -> str | None:
    """Reuse the user's existing GitHub credential without storing it in Iceywing."""
    for variable in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(variable, "").strip()
        if token:
            return token

    try:
        completed = subprocess.run(
            ["git", "credential", "fill"],
            input=b"protocol=https\nhost=github.com\n\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None

    fields: dict[str, str] = {}
    for raw_line in completed.stdout.decode("utf-8", errors="replace").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        fields[key.strip().lower()] = value.strip()
    return fields.get("password") or None


def _github_request(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    raw: bytes | None = None,
    content_type: str = "application/json",
) -> Any:
    if payload is not None and raw is not None:
        raise ValueError("Use payload or raw, not both.")
    body = json.dumps(payload).encode("utf-8") if payload is not None else raw
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Iceywing",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if body is not None:
        headers["Content-Type"] = content_type

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            parsed = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(parsed.get("message", "")).strip()
        except (json.JSONDecodeError, AttributeError):
            pass
        suffix = f": {detail}" if detail else ""
        raise IceywingError(f"GitHub API {method} failed ({exc.code}){suffix}") from exc
    except urllib.error.URLError as exc:
        raise IceywingError(f"Could not reach GitHub: {exc.reason}") from exc

    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return data


def _github_token_or_error() -> str:
    token = _credential_token()
    if token:
        return token
    raise IceywingError(
        "GitHub authentication was not found.\n"
        "Iceywing tried GITHUB_TOKEN, GH_TOKEN, and your existing Git credential.\n"
        "On Windows, a normal authenticated `git push` usually lets Git Credential Manager provide it.\n"
        "Otherwise set GITHUB_TOKEN for this shell and rerun the release."
    )


def _tag_exists(root: Path, tag: str) -> str | None:
    result = run(["git", "rev-list", "-n", "1", tag], cwd=root, check=False)
    sha = (result.stdout or "").strip()
    return sha or None


def _remote_tag_sha(root: Path, tag: str) -> str | None:
    result = run(["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"], cwd=root, check=False)
    line = (result.stdout or "").strip()
    return line.split()[0] if line else None


def _ensure_clean(repo: GitRepo, *, commit: bool, identity: ReleaseIdentity) -> str:
    if repo.clean():
        return repo.head()
    if not commit:
        raise IceywingError(
            "Release requires a clean working tree.\n"
            "Review and commit your changes first, or rerun with `--commit` to explicitly include them."
        )
    return repo.commit(f"Release {identity.title}")


def _push_head(repo: GitRepo) -> None:
    branch = repo.branch()
    if branch == "(detached)":
        raise IceywingError("Cannot release from detached HEAD.")
    run(["git", "push", "-u", "origin", branch], cwd=repo.root, capture=False)


def _ensure_tag(repo: GitRepo, tag: str) -> None:
    head = repo.head()
    local = _tag_exists(repo.root, tag)
    if local and local != head:
        raise IceywingError(f"Tag {tag} already points to a different commit ({local[:12]}).")
    if not local:
        run(["git", "tag", tag], cwd=repo.root)

    remote = _remote_tag_sha(repo.root, tag)
    if remote and remote != head:
        raise IceywingError(f"Remote tag {tag} already points to a different commit ({remote[:12]}).")
    if not remote:
        run(["git", "push", "origin", tag], cwd=repo.root, capture=False)


def _zip_source(root: Path, destination: Path, installer_wheel: Path | None = None) -> None:
    """Create the human-readable release ZIP.

    The source tree stays clean, but Windows Setup.bat is intentionally
    self-contained: when an installer wheel is supplied, exactly that wheel
    is embedded under dist/. Other local build artifacts remain excluded.
    """
    excluded_dirs = {
        ".git",
        ".venv",
        "venv",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        ".iceywing",
    }
    excluded_suffixes = {".pyc", ".pyo"}
    prefix = destination.stem
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if any(part in excluded_dirs or part.endswith(".egg-info") for part in rel.parts):
                continue
            if path.is_dir() or path.suffix in excluded_suffixes:
                continue
            archive.write(path, Path(prefix) / rel)

        if installer_wheel is not None:
            if not installer_wheel.is_file():
                raise IceywingError(f"Installer wheel not found: {installer_wheel}")
            archive.write(
                installer_wheel,
                Path(prefix) / "dist" / installer_wheel.name,
            )


def _build_artifacts(root: Path, identity: ReleaseIdentity) -> ReleaseArtifacts:
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)

    # Remove only artifacts for this exact version so unrelated local files survive.
    normalized = identity.project_name.lower().replace("-", "_")
    for old in dist.glob(f"{normalized}-{identity.package_version}-*.whl"):
        old.unlink()
    source_zip = dist / identity.archive_name
    if source_zip.exists():
        source_zip.unlink()

    run_logged(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "--wheel-dir", str(dist)],
        cwd=root,
        label="Build wheel",
        log_prefix="release-build",
        tail_lines=20,
    )
    wheels = sorted(dist.glob(f"{normalized}-{identity.package_version}-*.whl"))
    if not wheels:
        # setuptools normalizes names, but keep a safe fallback for unusual package names.
        wheels = sorted(dist.glob(f"*-{identity.package_version}-*.whl"))
    if len(wheels) != 1:
        raise IceywingError(f"Expected one wheel for {identity.package_version}, found {len(wheels)} in dist/.")

    _zip_source(root, source_zip, installer_wheel=wheels[0])
    return ReleaseArtifacts(source_zip=source_zip, wheel=wheels[0])


def _release_notes(identity: ReleaseIdentity) -> str:
    """Return GitHub-ready release notes without repeating the release title/date.

    GitHub already renders the release name and publication timestamp. Keeping those
    out of the body matches the concise format used by mature CLI projects and makes
    the first visible section the user-facing highlights.
    """
    if identity.notes_path:
        try:
            text = identity.notes_path.read_text(encoding="utf-8").strip()
            lines = text.splitlines()
            if lines and lines[0].startswith("# "):
                lines = lines[1:]
            while lines and not lines[0].strip():
                lines = lines[1:]
            if lines and lines[0].startswith("Released on "):
                lines = lines[1:]
            while lines and not lines[0].strip():
                lines = lines[1:]
            if lines:
                return "\n".join(lines).strip()
        except OSError:
            pass
    return "Released with Iceywing built-in release automation."


def _get_release_by_tag(repo_slug: str, tag: str, token: str) -> dict[str, Any] | None:
    url = f"{_GITHUB_API}/repos/{repo_slug}/releases/tags/{urllib.parse.quote(tag, safe='')}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Iceywing",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        detail = ""
        try:
            detail = str(json.loads(exc.read().decode("utf-8", errors="replace")).get("message", ""))
        except json.JSONDecodeError:
            pass
        raise IceywingError(f"GitHub release lookup failed ({exc.code}){': ' + detail if detail else ''}") from exc
    except urllib.error.URLError as exc:
        raise IceywingError(f"Could not reach GitHub: {exc.reason}") from exc


def _create_or_get_release(
    repo_slug: str,
    identity: ReleaseIdentity,
    *,
    head: str,
    token: str,
) -> dict[str, Any]:
    existing = _get_release_by_tag(repo_slug, identity.tag, token)
    if existing:
        return existing
    payload = {
        "tag_name": identity.tag,
        "target_commitish": head,
        "name": identity.title,
        "body": _release_notes(identity),
        "draft": False,
        "prerelease": identity.preview_number is not None,
        "make_latest": "false" if identity.preview_number is not None else "true",
    }
    result = _github_request(
        "POST",
        f"{_GITHUB_API}/repos/{repo_slug}/releases",
        token=token,
        payload=payload,
    )
    if not isinstance(result, dict):
        raise IceywingError("GitHub returned an unexpected release response.")
    return result


def _upload_asset(repo_slug: str, release: dict[str, Any], path: Path, token: str) -> None:
    release_id = release.get("id")
    if not release_id:
        raise IceywingError("GitHub release response did not include an id.")

    assets = _github_request(
        "GET",
        f"{_GITHUB_API}/repos/{repo_slug}/releases/{release_id}/assets",
        token=token,
    )
    if isinstance(assets, list) and any(item.get("name") == path.name for item in assets if isinstance(item, dict)):
        return

    query = urllib.parse.urlencode({"name": path.name})
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    _github_request(
        "POST",
        f"{_GITHUB_UPLOADS}/repos/{repo_slug}/releases/{release_id}/assets?{query}",
        token=token,
        raw=path.read_bytes(),
        content_type=content_type,
    )


def publish(
    config: ProjectConfig,
    *,
    dry_run: bool = False,
    commit: bool = False,
) -> None:
    """Publish the current package as a GitHub Release.

    Alpha versions are published as pre-releases; stable versions are published normally.
    Release is intentionally conservative: a dirty tree is rejected unless the user
    explicitly passes --commit, and credentials are reused from the environment or
    Git Credential Manager rather than persisted by Iceywing.
    """
    repo = GitRepo.discover(config.root)
    identity = _release_identity(repo.root)
    repo_slug = _origin_repo(repo.root)
    branch = repo.branch()
    if branch == "(detached)":
        raise IceywingError("Cannot release from detached HEAD.")

    print(f"* Release · {identity.title}\n")

    if dry_run:
        dirty = not repo.clean()
        print(f"{concise_mark('ok')} Mode     dry-run (no GitHub or Git writes)")
        print(f"{concise_mark('ok')} Repo     {repo_slug}")
        print(f"{concise_mark('ok')} Branch   {branch}")
        print(f"{concise_mark('ok')} Tag      {identity.tag}")
        print(f"{concise_mark('ok')} Release  {'pre-release' if identity.preview_number is not None else 'release'}")
        print(f"{concise_mark('warn') if dirty else concise_mark('ok')} Tree     {'changes would be committed' if dirty and commit else 'dirty' if dirty else 'clean'}")
        print(f"{concise_mark('ok')} Asset    {identity.archive_name}")
        print("\nDry run complete.")
        return

    head = _ensure_clean(repo, commit=commit, identity=identity)
    print(f"{concise_mark('ok')} Source   {head[:12]}")

    verify_result = environment.verify(config, quiet=True)
    print(format_summary(verify_result, mark=concise_mark("ok")))

    artifacts = _build_artifacts(repo.root, identity)
    print(f"{concise_mark('ok')} Build    {artifacts.source_zip.name} · {artifacts.wheel.name}")

    _push_head(repo)
    print(f"{concise_mark('ok')} Push     origin/{branch}")

    _ensure_tag(repo, identity.tag)
    print(f"{concise_mark('ok')} Tag      {identity.tag}")

    token = _github_token_or_error()
    release = _create_or_get_release(repo_slug, identity, head=repo.head(), token=token)
    print(f"{concise_mark('ok')} Release  GitHub · {'pre-release' if identity.preview_number is not None else 'published'}")

    _upload_asset(repo_slug, release, artifacts.source_zip, token)
    print(f"{concise_mark('ok')} Upload   {artifacts.source_zip.name}")

    url = str(release.get("html_url") or f"https://github.com/{repo_slug}/releases/tag/{identity.tag}")
    print(f"\nDone: {identity.tag}")
    print(url)


def preview(config: ProjectConfig, *, dry_run: bool = False, commit: bool = False) -> None:
    """Compatibility alias for Preview25/26 scripts. Prefer ``release publish``."""
    publish(config, dry_run=dry_run, commit=commit)
