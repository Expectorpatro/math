"""Concentrated, measured post-processing of Quarto's rendered HTML."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import html
from pathlib import Path
import posixpath
import re
from typing import Callable
from urllib.parse import unquote, urlsplit

from .errors import BuildError
from .images import jpeg_dimensions, png_dimensions, svg_dimensions


@dataclass(frozen=True, slots=True)
class PostprocessReport:
    index_replacements: int
    reference_pages_changed: int
    metadata_pages_changed: int
    favicon_pages_changed: int
    image_alt_attributes_added: int
    image_dimension_pairs_added: int
    resource_ids_rewritten: int

    def as_dict(self) -> dict[str, int]:
        return {
            "index_replacements": self.index_replacements,
            "reference_pages_changed": self.reference_pages_changed,
            "metadata_pages_changed": self.metadata_pages_changed,
            "favicon_pages_changed": self.favicon_pages_changed,
            "image_alt_attributes_added": self.image_alt_attributes_added,
            "image_dimension_pairs_added": self.image_dimension_pairs_added,
            "resource_ids_rewritten": self.resource_ids_rewritten,
        }


def remove_div_by_id(markup: str, identifier: str) -> str:
    """Remove one balanced ``div`` from generated markup by identifier."""

    start_match = re.search(
        rf'<div\b(?=[^>]*\bid=["\']{re.escape(identifier)}["\'])[^>]*>',
        markup,
        flags=re.IGNORECASE,
    )
    if not start_match:
        return markup
    depth = 0
    for tag_match in re.finditer(
        r"</?div\b[^>]*>", markup[start_match.start() :], re.IGNORECASE
    ):
        tag = tag_match.group(0)
        if tag.lower().startswith("</div"):
            depth -= 1
            if depth == 0:
                start = start_match.start()
                end = start_match.start() + tag_match.end()
                return markup[:start].rstrip() + "\n\n" + markup[end:].lstrip()
        elif not tag.endswith("/>"):
            depth += 1
    return markup


class RenderedSitePostprocessor:
    """Apply the unavoidable Quarto-output adjustments in one audited place."""

    def __init__(self, warning: Callable[[str], None] | None = None) -> None:
        self.warning = warning

    def process(
        self, output_dir: Path, site_metadata: dict[str, str]
    ) -> PostprocessReport:
        index_changes = self._process_index(output_dir)
        references = self._process_reference_pages(output_dir)
        (
            metadata,
            image_alts,
            image_dimensions,
            resource_ids,
        ) = self._process_site_markup(output_dir, site_metadata)
        favicons = self._cache_bust_favicon(output_dir)
        return PostprocessReport(
            index_changes,
            references,
            metadata,
            favicons,
            image_alts,
            image_dimensions,
            resource_ids,
        )

    def _process_index(self, output_dir: Path) -> int:
        index = output_dir / "index.html"
        if not index.is_file():
            raise BuildError("Quarto 未生成首页 index.html")
        markup = index.read_text(encoding="utf-8")
        updated, navigation_count = re.subn(
            r'<nav class="page-navigation">.*?</nav>',
            "",
            markup,
            flags=re.IGNORECASE | re.DOTALL,
        )
        replacements = navigation_count
        exact_replacements = (
            (
                '<div class="textbook-home page-columns page-full">',
                '<div class="textbook-home">',
            ),
            (
                '<section class="home-intro page-columns page-full"',
                '<section class="home-intro"',
            ),
            (
                '<div class="quarto-title-meta-heading">修改于</div>',
                '<div class="quarto-title-meta-heading">编译于</div>',
            ),
            (
                '<div class="quarto-title-meta-heading">Modified</div>',
                '<div class="quarto-title-meta-heading">编译于</div>',
            ),
        )
        for source, destination in exact_replacements:
            count = updated.count(source)
            replacements += count
            updated = updated.replace(source, destination)
        if replacements == 0 and self.warning:
            self.warning("首页未匹配任何预期的 Quarto 后处理标记")
        if updated != markup:
            index.write_text(updated, encoding="utf-8")
        return replacements

    @staticmethod
    def _process_reference_pages(output_dir: Path) -> int:
        references_page = output_dir / "references.html"
        if not references_page.exists():
            return 0
        relative_reference = references_page.relative_to(output_dir).as_posix()
        changed = 0
        for path in sorted(output_dir.rglob("*.html")):
            markup = path.read_text(encoding="utf-8")
            if path.resolve() == references_page.resolve():
                updated = markup
            else:
                current = path.parent.relative_to(output_dir).as_posix()
                if current == ".":
                    current = ""
                target = posixpath.relpath(
                    relative_reference, start=current or "."
                )
                updated = re.sub(
                    r'href="#(ref-[^"]+)"',
                    rf'href="{target}#\1"',
                    markup,
                )
                updated = remove_div_by_id(updated, "refs")
            if updated != markup:
                path.write_text(updated, encoding="utf-8")
                changed += 1
        return changed

    @staticmethod
    def _image_source(tag: str) -> str | None:
        match = re.search(
            r"\bsrc\s*=\s*([\"'])(.*?)\1",
            tag,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return html.unescape(match.group(2)) if match else None

    @staticmethod
    def _dimensions_from_bytes(
        data: bytes, image_format: str
    ) -> tuple[int, int] | None:
        normalized = image_format.lower().removeprefix("image/")
        if normalized == "png":
            dimensions = png_dimensions(data)
            return (
                (dimensions.width, dimensions.height)
                if dimensions is not None
                else None
            )
        if normalized in {"jpeg", "jpg"}:
            dimensions = jpeg_dimensions(data)
            return (
                (dimensions.width, dimensions.height)
                if dimensions is not None
                else None
            )
        if normalized in {"svg", "svg+xml"}:
            dimensions = svg_dimensions(data.decode("utf-8", errors="replace"))
            return (
                (round(dimensions[0]), round(dimensions[1]))
                if dimensions is not None
                else None
            )
        return None

    @classmethod
    def _embedded_image_dimensions(cls, source: str) -> tuple[int, int] | None:
        header, separator, encoded = source.partition(",")
        if not separator or not header.lower().startswith("data:image/"):
            return None
        metadata = header[5:].split(";")
        if "base64" not in {item.lower() for item in metadata[1:]}:
            return None
        try:
            data = base64.b64decode(
                re.sub(r"\s+", "", encoded), validate=True
            )
        except (ValueError, binascii.Error):
            return None
        return cls._dimensions_from_bytes(data, metadata[0])

    @classmethod
    def _local_image_dimensions(
        cls,
        source: str,
        *,
        page: Path,
        output_dir: Path,
    ) -> tuple[int, int] | None:
        parsed = urlsplit(source)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return None
        target = (page.parent / unquote(parsed.path)).resolve()
        try:
            target.relative_to(output_dir.resolve())
        except ValueError:
            return None
        if not target.is_file():
            return None
        suffix = target.suffix.lower().lstrip(".")
        if suffix not in {"png", "jpg", "jpeg", "svg"}:
            return None
        try:
            data = target.read_bytes()
        except OSError:
            return None
        return cls._dimensions_from_bytes(data, suffix)

    @staticmethod
    def _fallback_alt(tag: str, source: str | None) -> str:
        class_match = re.search(
            r"\bclass\s*=\s*([\"'])(.*?)\1",
            tag,
            flags=re.IGNORECASE | re.DOTALL,
        )
        classes = set(class_match.group(2).split()) if class_match else set()
        if "tikz-image" in classes:
            return "TikZ 数学图示"
        if source and source.lower().startswith("data:image/"):
            return "计算实验图"
        if source:
            stem = Path(unquote(urlsplit(source).path)).stem
            label = re.sub(r"[-_]+", " ", stem).strip()
            if label:
                return f"插图：{label}"
        return "教材插图"

    @classmethod
    def _optimize_image(
        cls,
        match: re.Match[str],
        *,
        page: Path,
        output_dir: Path,
        counters: dict[str, int],
    ) -> str:
        tag = match.group(0)
        closing = "/>" if tag.endswith("/>") else ">"
        core = tag[: -len(closing)].rstrip()
        source = cls._image_source(tag)
        embedded = bool(source and source.lower().startswith("data:image/"))
        dimensions = (
            cls._embedded_image_dimensions(source)
            if embedded and source is not None
            else cls._local_image_dimensions(
                source or "", page=page, output_dir=output_dir
            )
        )
        if dimensions is not None:
            natural_width, natural_height = dimensions
            width_match = re.search(
                r"\bwidth\s*=\s*([\"'])(\d+)\1", tag, re.IGNORECASE
            )
            height_match = re.search(
                r"\bheight\s*=\s*([\"'])(\d+)\1", tag, re.IGNORECASE
            )
            has_width = bool(
                re.search(r"\bwidth\s*=", tag, re.IGNORECASE)
            )
            has_height = bool(
                re.search(r"\bheight\s*=", tag, re.IGNORECASE)
            )
            dimension_added = False
            if not has_width and not has_height:
                core += f' width="{natural_width}" height="{natural_height}"'
                dimension_added = True
            elif width_match is not None and not has_height:
                displayed_width = int(width_match.group(2))
                displayed_height = max(
                    1,
                    round(
                        displayed_width * natural_height / natural_width
                    ),
                )
                core += f' height="{displayed_height}"'
                dimension_added = True
            elif height_match is not None and not has_width:
                displayed_height = int(height_match.group(2))
                displayed_width = max(
                    1,
                    round(
                        displayed_height * natural_width / natural_height
                    ),
                )
                core += f' width="{displayed_width}"'
                dimension_added = True
            if dimension_added:
                counters["dimensions"] += 1
        if not re.search(r"\balt\s*=", tag, re.IGNORECASE):
            alt = html.escape(cls._fallback_alt(tag, source), quote=True)
            core += f' alt="{alt}"'
            counters["alts"] += 1
        if not re.search(r"\bloading\s*=", tag, re.IGNORECASE):
            core += f' loading="{"eager" if embedded else "lazy"}"'
        if not re.search(r"\bdecoding\s*=", tag, re.IGNORECASE):
            core += ' decoding="async"'
        return core + closing

    @staticmethod
    def _deduplicate_quarto_resource_ids(markup: str) -> tuple[str, int]:
        """Give Quarto theme links unique IDs without changing its selectors."""

        changed = 0
        for identifier in (
            "quarto-text-highlighting-styles",
            "quarto-bootstrap",
        ):
            pattern = re.compile(
                rf"<link\b(?=[^>]*\bid=([\"']){re.escape(identifier)}\1)[^>]*>",
                flags=re.IGNORECASE,
            )
            matches = pattern.findall(markup)
            if len(matches) <= 1:
                continue
            variant_counts: dict[str, int] = {}

            def replace(match: re.Match[str]) -> str:
                nonlocal changed
                tag = match.group(0)
                if "quarto-color-scheme-extra" in tag:
                    return tag
                variant = (
                    "alternate"
                    if "quarto-color-alternate" in tag
                    else "default"
                )
                variant_counts[variant] = variant_counts.get(variant, 0) + 1
                suffix = (
                    variant
                    if variant_counts[variant] == 1
                    else f"{variant}-{variant_counts[variant]}"
                )
                changed += 1
                return re.sub(
                    rf"(\bid=)([\"']){re.escape(identifier)}\2",
                    rf"\1\2{identifier}-{suffix}\2",
                    tag,
                    count=1,
                    flags=re.IGNORECASE,
                )

            markup = pattern.sub(replace, markup)
        return markup, changed

    @classmethod
    def _process_site_markup(
        cls, output_dir: Path, site_metadata: dict[str, str]
    ) -> tuple[int, int, int, int]:
        repository_meta = (
            '<meta name="textbook-repository" content="'
            + html.escape(site_metadata["repository"], quote=True)
            + '">\n'
        )
        changed = 0
        counters = {"alts": 0, "dimensions": 0, "resource_ids": 0}
        for path in sorted(output_dir.rglob("*.html")):
            markup = path.read_text(encoding="utf-8")
            updated = markup
            if 'name="textbook-repository"' not in updated:
                updated = updated.replace("</head>", repository_meta + "</head>", 1)
            updated, rewritten_ids = cls._deduplicate_quarto_resource_ids(
                updated
            )
            counters["resource_ids"] += rewritten_ids
            updated = re.sub(
                r"<img\b[^>]*>",
                lambda match: cls._optimize_image(
                    match,
                    page=path,
                    output_dir=output_dir,
                    counters=counters,
                ),
                updated,
                flags=re.IGNORECASE,
            )
            if updated != markup:
                path.write_text(updated, encoding="utf-8")
                changed += 1
        return (
            changed,
            counters["alts"],
            counters["dimensions"],
            counters["resource_ids"],
        )

    @staticmethod
    def _cache_bust_favicon(output_dir: Path) -> int:
        favicon = output_dir / "favicon.svg"
        if not favicon.is_file():
            return 0
        version = hashlib.sha256(favicon.read_bytes()).hexdigest()[:12]
        icon_link = re.compile(
            r'(<link\b(?=[^>]*\brel=["\']icon["\'])[^>]*\bhref=["\'])'
            r'([^"\']*favicon\.svg)(?:\?[^"\']*)?(["\'])',
            flags=re.IGNORECASE,
        )
        changed = 0
        for path in sorted(output_dir.rglob("*.html")):
            markup = path.read_text(encoding="utf-8")
            updated = icon_link.sub(rf"\1\2?v={version}\3", markup)
            if updated != markup:
                path.write_text(updated, encoding="utf-8")
                changed += 1
        return changed


__all__ = ["PostprocessReport", "RenderedSitePostprocessor", "remove_div_by_id"]
