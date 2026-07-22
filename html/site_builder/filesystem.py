"""Safe filesystem operations for generated directories."""

from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
import shutil
import uuid

from .errors import BuildError


def is_strict_descendant(path: Path, parent: Path) -> bool:
    """Return whether *path* is below, but not equal to, *parent*."""

    path = path.resolve()
    parent = parent.resolve()
    try:
        relative = path.relative_to(parent)
    except ValueError:
        return False
    return bool(relative.parts)


def ensure_within(path: Path, parent: Path, *, label: str) -> Path:
    """Resolve a path and require it to remain inside a trusted directory."""

    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as error:
        raise BuildError(f"{label}路径越界：{path}") from error
    return resolved


def _ensure_managed(path: Path, managed: Iterable[Path]) -> Path:
    resolved = path.resolve()
    allowed = {item.resolve() for item in managed}
    if resolved not in allowed:
        raise BuildError(f"拒绝清理未登记的生成目录：{resolved}")
    return resolved


def prepare_empty_directory(path: Path, *, managed: Iterable[Path]) -> None:
    """Recreate one explicitly registered generated directory."""

    resolved = _ensure_managed(path, managed)
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def _looks_like_legacy_generated_site(path: Path) -> bool:
    """Recognize the project's pre-marker publication layout.

    Older versions of the builder published directly to ``html/site`` without
    an ownership marker.  The fingerprint deliberately requires several
    generated-site files so an arbitrary directory is still protected from
    replacement.
    """

    required_entries = (
        ".nojekyll",
        "index.html",
        "chapters",
        "search.json",
        "sitemap.xml",
    )
    return all((path / entry).exists() for entry in required_entries)


def _is_replaceable_publication_directory(path: Path) -> bool:
    """Return whether *path* is a current or recognized legacy site output."""

    return (
        (path / ".generated-site").is_file()
        or (path / ".textbook-generated-site").is_file()
        or _looks_like_legacy_generated_site(path)
    )


def atomic_publish_directory(
    source: Path,
    destination: Path,
    *,
    html_dir: Path,
    protected: Iterable[Path],
) -> tuple[str, ...]:
    """Publish a complete directory with rollback on replacement failure.

    The new tree is copied beside the destination first.  The old publication
    is moved to a temporary backup only after the copy succeeds, and is restored
    if the final rename fails.
    """

    source = source.resolve()
    destination = destination.resolve()
    html_dir = html_dir.resolve()
    if not source.is_dir():
        raise BuildError(f"待发布站点不存在：{source}")
    if not (source / ".generated-site").is_file():
        raise BuildError("待发布目录缺少生成站点标记")
    if not is_strict_descendant(destination, html_dir):
        raise BuildError("发布目录必须是 html/ 的严格子目录")
    for item in protected:
        protected_path = item.resolve()
        overlaps = (
            destination == protected_path
            or destination.is_relative_to(protected_path)
            or protected_path.is_relative_to(destination)
        )
        if overlaps:
            raise BuildError(
                "发布目录不能与受保护路径重叠："
                f"{destination} ↔ {protected_path}"
            )

    if destination.exists() and any(destination.iterdir()):
        if not _is_replaceable_publication_directory(destination):
            raise BuildError(
                f"拒绝覆盖非构建系统管理的非空目录：{destination}"
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    incoming = destination.parent / f".{destination.name}.incoming-{token}"
    backup = destination.parent / f".{destination.name}.backup-{token}"
    try:
        shutil.copytree(source, incoming)
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(incoming, destination)
        except Exception:
            if backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
    except Exception as error:
        if incoming.exists():
            shutil.rmtree(incoming)
        if backup.exists() and not destination.exists():
            os.replace(backup, destination)
        if isinstance(error, BuildError):
            raise
        raise BuildError(f"发布站点失败：{error}") from error

    cleanup_warnings: list[str] = []
    if backup.exists():
        try:
            shutil.rmtree(backup)
        except OSError as error:
            cleanup_warnings.append(f"旧站点备份未能清理：{backup}（{error}）")
    return tuple(cleanup_warnings)
