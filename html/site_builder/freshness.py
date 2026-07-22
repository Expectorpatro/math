"""Deterministic source fingerprints for committed static-site publication."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
from typing import Iterable

from .errors import BuildError


FINGERPRINT_FILENAME = ".source-fingerprint"
FINGERPRINT_SCHEMA = "site-source-sha256-v1"

_EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".quarto",
        ".qmd-cache",
        ".qmd-temp",
        "__pycache__",
        "_minted",
    }
)
_BOOK_INPUT_SUFFIXES = frozenset(
    {
        ".avif",
        ".bib",
        ".bst",
        ".c",
        ".cc",
        ".cls",
        ".cpp",
        ".csv",
        ".gif",
        ".h",
        ".hpp",
        ".ico",
        ".jpeg",
        ".jpg",
        ".jl",
        ".json",
        ".lua",
        ".m",
        ".mat",
        ".mp3",
        ".mp4",
        ".otf",
        ".pdf",
        ".png",
        ".py",
        ".r",
        ".sh",
        ".sty",
        ".svg",
        ".tex",
        ".ttf",
        ".tsv",
        ".txt",
        ".vtt",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
    }
)
_ROOT_BUILD_INPUTS = frozenset({".Rprofile", "renv.lock"})


def is_site_source_path(
    relative_path: Path,
    *,
    output_relative: Path = Path("html/site"),
) -> bool:
    """Return whether a repository-relative path can affect generated HTML.

    The rules intentionally favor a conservative rebuild over a stale
    deployment. Generated output, tests, documentation, caches, and local
    environments are excluded; the LaTeX book, website builder/assets, and
    computation inputs are included.
    """

    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("source fingerprint paths must be repository-relative")
    parts = relative_path.parts
    if not parts or relative_path.name == ".DS_Store":
        return False
    if any(part in _EXCLUDED_DIRECTORY_NAMES for part in parts):
        return False
    if parts[0] == "skills" or parts[:2] == ("renv", "library"):
        return False
    if parts[:2] == ("html", ".build"):
        return False
    if relative_path == output_relative or relative_path.is_relative_to(
        output_relative
    ):
        return False
    if parts[:2] == ("html", "tests"):
        return False
    if parts[0] == ".github":
        return False
    if relative_path.name.casefold() == "readme.md":
        return False

    if parts[0] == "html":
        return True
    if parts[0] in {"environment", "figure_settings", "renv"}:
        return True
    if relative_path.as_posix() in _ROOT_BUILD_INPUTS:
        return True
    if "computations" in parts or relative_path.name == "computations.order":
        return True
    return relative_path.suffix.casefold() in _BOOK_INPUT_SUFFIXES


def _git_worktree_paths(project_root: Path) -> list[Path]:
    """List tracked and non-ignored untracked files from the working tree."""

    try:
        completed = subprocess.run(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            cwd=project_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise BuildError(
            "无法读取 Git 工作区，不能生成站点源码指纹"
        ) from error
    return [
        Path(os.fsdecode(raw_path))
        for raw_path in completed.stdout.split(b"\0")
        if raw_path
    ]


def source_fingerprint(
    project_root: Path,
    candidate_paths: Iterable[Path] | None = None,
    *,
    output_dir: Path | None = None,
) -> str:
    """Hash current build inputs using stable path and content framing."""

    project_root = project_root.resolve()
    candidates = (
        _git_worktree_paths(project_root)
        if candidate_paths is None
        else list(candidate_paths)
    )
    resolved_output = (
        (project_root / "html" / "site").resolve()
        if output_dir is None
        else output_dir.resolve()
    )
    try:
        output_relative = resolved_output.relative_to(project_root)
    except ValueError as error:
        raise BuildError("站点输出目录必须位于项目目录内") from error
    selected: dict[str, Path] = {}
    for candidate in candidates:
        relative = Path(candidate)
        if relative.is_absolute():
            try:
                relative = relative.resolve().relative_to(project_root)
            except ValueError as error:
                raise BuildError(f"站点源码路径逃出项目目录：{candidate}") from error
        if not is_site_source_path(
            relative,
            output_relative=output_relative,
        ):
            continue
        source = project_root / relative
        # A deleted tracked file should have the same effective file set as it
        # does after the deletion is committed.
        if not source.exists() and not source.is_symlink():
            continue
        selected[relative.as_posix()] = source

    digest = hashlib.sha256()
    digest.update(f"{FINGERPRINT_SCHEMA}\0".encode("ascii"))
    for relative_name in sorted(selected):
        source = selected[relative_name]
        if source.is_symlink():
            kind = b"symlink"
            payload = os.fsencode(os.readlink(source))
        elif source.is_file():
            kind = b"file"
            payload = source.read_bytes()
        else:
            continue
        name = relative_name.encode("utf-8", errors="surrogateescape")
        for component in (kind, name, payload):
            digest.update(len(component).to_bytes(8, "big"))
            digest.update(component)
    return digest.hexdigest()


def fingerprint_record(digest: str) -> str:
    """Serialize a fingerprint without publishing source names or diagnostics."""

    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError("fingerprint must be a lowercase SHA-256 digest")
    return f"{FINGERPRINT_SCHEMA}:{digest}\n"


def write_site_fingerprint(
    project_root: Path,
    marker_dir: Path,
    candidate_paths: Iterable[Path] | None = None,
    *,
    output_dir: Path | None = None,
) -> str:
    """Write the current source digest into a generated site's hidden marker."""

    digest = source_fingerprint(
        project_root,
        candidate_paths,
        output_dir=marker_dir if output_dir is None else output_dir,
    )
    marker = marker_dir / FINGERPRINT_FILENAME
    marker.write_text(fingerprint_record(digest), encoding="ascii")
    return digest


def verify_site_fingerprint(
    project_root: Path,
    site_dir: Path,
    candidate_paths: Iterable[Path] | None = None,
) -> str:
    """Raise when a committed site does not match current build inputs."""

    marker = site_dir / FINGERPRINT_FILENAME
    if not marker.is_file():
        raise BuildError(
            f"发布目录缺少 {FINGERPRINT_FILENAME}；请先运行 python3 html/build.py"
        )
    expected = fingerprint_record(
        source_fingerprint(
            project_root,
            candidate_paths,
            output_dir=site_dir,
        )
    )
    try:
        actual = marker.read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise BuildError(f"无法读取站点源码指纹：{marker}") from error
    if actual != expected:
        try:
            display_site = site_dir.resolve().relative_to(
                project_root.resolve()
            )
        except ValueError:
            display_site = site_dir
        raise BuildError(
            f"{display_site} 与当前网页源码不一致；请重新运行 "
            "python3 html/build.py 并提交新的站点文件"
        )
    return expected.removeprefix(f"{FINGERPRINT_SCHEMA}:").strip()
