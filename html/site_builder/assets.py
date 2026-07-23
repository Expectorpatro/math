"""Discovery and byte-preserving publication of website resources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Any
from urllib.parse import unquote, urlsplit

from .config import BuildConfig
from .errors import BuildError
from .filesystem import ensure_within


class AssetManager:
    """Copy author assets unchanged and materialize generated web assets."""

    def __init__(self, config: BuildConfig) -> None:
        self.config = config

    def prepare(self, document: dict[str, Any]) -> int:
        prepared = 0
        for target in sorted(self._pandoc_image_targets(document)):
            self._copy_content_image(target)
            prepared += 1
        self._build_style_bundle()
        prepared += 1
        versions: dict[str, str] = {}
        public_sources = self.config.assets.public_sources
        public_files = self.config.assets.public_files
        citation_source = self.config.assets.citation_style_source
        citation_style = self.config.assets.citation_style
        if citation_style in public_files:
            raise BuildError("引用样式不得同时出现在 assets.public_sources 中")
        if len(set(public_files)) != len(public_files):
            raise BuildError("公开网页资源的文件名不得重复")
        for source_name, public_name in zip(public_sources, public_files):
            versions[public_name] = self._copy_asset(source_name, public_name)
            prepared += 1
        self._copy_asset(citation_source, citation_style)
        prepared += 1
        self._render_header(versions)
        return prepared + 1

    def _copy_asset(self, source_name: str, public_name: str) -> str:
        source = self.config.paths.html_asset(source_name)
        if not source.is_file():
            raise BuildError(f"缺少网页资源：{source}")
        destination = self.config.paths.quarto_project_dir / public_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return hashlib.sha256(source.read_bytes()).hexdigest()[:12]

    def _build_style_bundle(self) -> None:
        """Assemble ordered CSS modules into Quarto's single theme asset.

        Keeping the cascade order in configuration makes the source stylesheet
        maintainable without changing the public ``style.css`` URL.
        """

        configured_sources = self.config.assets.style_sources
        if not configured_sources:
            raise BuildError("assets.style_sources 不得为空")
        parts: list[str] = []
        for name in configured_sources:
            source = self.config.paths.html_asset(name)
            if not source.is_file():
                raise BuildError(f"缺少 CSS 模块：{source}")
            parts.append(source.read_text(encoding="utf-8"))
        bundle = "".join(parts)
        destination = ensure_within(
            self.config.paths.quarto_project_dir / self.config.assets.style_bundle,
            self.config.paths.quarto_project_dir,
            label="CSS 输出",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(bundle, encoding="utf-8")

    def _copy_content_image(self, target: str) -> None:
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

    def _render_header(self, versions: dict[str, str]) -> None:
        source = self.config.paths.html_asset(
            self.config.assets.header_template_source
        )
        template = source.read_text(encoding="utf-8")
        placeholder = "__TEXTBOOK_ASSET_VERSIONS__"
        count = template.count(placeholder)
        if count != 1:
            raise BuildError(
                f"{source.name} 中 {placeholder} 应恰好出现一次，实际 {count} 次"
            )
        template = template.replace(
            placeholder,
            json.dumps(versions, ensure_ascii=False, sort_keys=True),
        )
        destination = self.config.paths.quarto_project_dir / source.name
        destination.write_text(template, encoding="utf-8")

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
