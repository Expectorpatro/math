"""Discovery and byte-preserving publication of website resources."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import shutil
from typing import Any
from urllib.parse import unquote, urlsplit

from .commands import CommandRunner
from .config import BuildConfig
from .errors import BuildError
from .filesystem import ensure_within


@dataclass(frozen=True, slots=True)
class AssetManifestEntry:
    source: Path
    destination: Path
    digest: str
    generated: bool = False


class AssetManager:
    """Copy author assets unchanged and materialize generated web assets."""

    def __init__(self, config: BuildConfig, runner: CommandRunner) -> None:
        self.config = config
        self.runner = runner

    def prepare(self, document: dict[str, Any]) -> list[AssetManifestEntry]:
        manifest: list[AssetManifestEntry] = []
        for target in sorted(self._pandoc_image_targets(document)):
            manifest.append(self._copy_content_image(target))
        manifest.append(self._build_style_bundle())
        versions: dict[str, str] = {}
        for name in self.config.assets.copy:
            source = self.config.paths.html_asset(name)
            if not source.is_file():
                raise BuildError(f"缺少网页资源：{source}")
            destination = self.config.paths.quarto_project_dir / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
            versions[name] = digest
            manifest.append(
                AssetManifestEntry(source, destination, digest, generated=False)
            )
        manifest.append(self._render_header(versions))
        return manifest

    def _build_style_bundle(self) -> AssetManifestEntry:
        """Assemble ordered CSS modules into Quarto's single theme asset.

        Keeping the cascade order in configuration makes the source stylesheet
        maintainable without changing the public ``style.css`` URL.
        """

        configured_sources = self.config.assets.style_sources
        if not configured_sources:
            raise BuildError("assets.style_sources 不得为空")
        sources: list[Path] = []
        parts: list[str] = []
        for name in configured_sources:
            source = self.config.paths.html_asset(name)
            if not source.is_file():
                raise BuildError(f"缺少 CSS 模块：{source}")
            sources.append(source)
            parts.append(source.read_text(encoding="utf-8"))
        bundle = "".join(parts)
        destination = ensure_within(
            self.config.paths.quarto_project_dir / self.config.assets.style_bundle,
            self.config.paths.quarto_project_dir,
            label="CSS 输出",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(bundle, encoding="utf-8")
        digest = hashlib.sha256(bundle.encode("utf-8")).hexdigest()[:12]
        return AssetManifestEntry(
            source=sources[0].parent,
            destination=destination,
            digest=digest,
            generated=True,
        )

    def _copy_content_image(self, target: str) -> AssetManifestEntry:
        """Copy one referenced image without decoding or resampling it."""

        paths = self.config.paths
        decoded_target = unquote(target)
        pure = PurePosixPath(decoded_target)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            raise BuildError(f"正文图片路径不安全：{target}")
        relative = Path(*pure.parts)
        candidates = (
            paths.staged_source_dir / relative,
            paths.project_root / relative,
        )
        source: Path | None = None
        for candidate in candidates:
            try:
                resolved = ensure_within(
                    candidate,
                    paths.staged_source_dir
                    if candidate.is_relative_to(paths.staged_source_dir)
                    else paths.project_root,
                    label="正文图片",
                )
            except BuildError:
                continue
            if resolved.is_file():
                source = resolved
                break
        if source is None:
            raise BuildError(f"找不到正文图片：{target}")
        destination = ensure_within(
            paths.quarto_project_dir / relative,
            paths.quarto_project_dir,
            label="图片输出",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        return AssetManifestEntry(
            source=source,
            destination=destination,
            digest=digest,
            generated="_tikz" in relative.parts,
        )

    def _render_header(self, versions: dict[str, str]) -> AssetManifestEntry:
        source = self.config.paths.html_asset(
            self.config.assets.header_template
        )
        template = source.read_text(encoding="utf-8")
        replacements = {
            placeholder: versions[asset_name]
            for placeholder, asset_name in self.config.assets.version_placeholders
        }
        for placeholder, value in replacements.items():
            count = template.count(placeholder)
            if count != 1:
                raise BuildError(
                    f"{source.name} 中 {placeholder} 应恰好出现一次，实际 {count} 次"
                )
            template = template.replace(placeholder, value)
        destination = self.config.paths.quarto_project_dir / source.name
        destination.write_text(template, encoding="utf-8")
        digest = hashlib.sha256(template.encode("utf-8")).hexdigest()[:12]
        return AssetManifestEntry(source, destination, digest, generated=True)

    @staticmethod
    def _pandoc_image_targets(document: dict[str, Any]) -> set[str]:
        targets: set[str] = set()

        def visit(value: Any) -> None:
            if isinstance(value, list):
                for item in value:
                    visit(item)
                return
            if not isinstance(value, dict):
                return
            if value.get("t") == "Image":
                target = value["c"][2][0]
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or target.startswith("//"):
                    raise BuildError(f"正文图片必须是项目内本地文件：{target}")
                targets.add(target)
            for item in value.values():
                visit(item)

        visit(document)
        return targets
