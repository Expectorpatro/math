"""Import self-contained computation results into rendered textbook pages.

Computation results are produced by Jupyter or Quarto as standalone HTML
documents.  This module extracts their semantic body, validates that every
embedded resource is self-contained, namespaces fragment identifiers, and
builds the appendix markup consumed by the book renderer.

The parser deliberately uses :class:`html.parser.HTMLParser` rather than
regular expressions for HTML structure.  This makes nested elements,
attribute quoting, SVG fragment references, and accessibility ID references
predictable while keeping the project free of another runtime dependency.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
import html
import math
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from .errors import BuildError
from .images import GeneratedImageInfo, inspect_data_image
from .markup import Markup, element, join, raw, text
from .computation_dom import (
    ComputationGroupLike,
    ComputationPage,
    _CaseCollector,
    _Comment,
    _CSS_URL,
    _DOCUMENT_ONLY_ELEMENTS,
    _Element,
    _Entity,
    _FORBIDDEN_ATTRIBUTES,
    _FORBIDDEN_ELEMENTS,
    _FRAGMENT_ATTRIBUTES,
    _MULTIPLE_IDREF_ATTRIBUTES,
    _Node,
    _REMOVED_ELEMENTS,
    _RESOURCE_ATTRIBUTES,
    _SINGLE_IDREF_ATTRIBUTES,
    _SrcsetCandidate,
    _StructureLocator,
    _SVG_FRAGMENT_RESOURCE_TAGS,
    _SVG_IMAGE_TAGS,
    _Text,
    _TreeParser,
    _VALID_PREFIX,
    _VOID_ELEMENTS,
)




class ComputationImporter:
    """Validate and import standalone computation-result HTML documents."""

    def __init__(
        self,
        *,
        project_root: Path,
        quarto_project_dir: Path,
        minimum_raster_width: int = 1,
        minimum_pixel_ratio: float = 1.0,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        if minimum_raster_width < 1:
            raise ValueError("minimum_raster_width must be positive")
        if not math.isfinite(minimum_pixel_ratio) or minimum_pixel_ratio <= 0:
            raise ValueError("minimum_pixel_ratio must be finite and positive")
        self.project_root = project_root.resolve()
        self.quarto_project_dir = quarto_project_dir.resolve()
        self.minimum_raster_width = minimum_raster_width
        self.minimum_pixel_ratio = minimum_pixel_ratio
        self.logger = logger

    def extract_fragment(
        self,
        result_path: Path,
        prefix: str,
        *,
        image_alt_prefix: str = "计算结果图",
    ) -> str:
        """Extract, sanitize, validate, and namespace one result document."""

        resolved = result_path.resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError as error:
            raise BuildError(
                f"数值计算结果必须位于项目目录内：{resolved}"
            ) from error
        if not resolved.is_file():
            raise BuildError(f"数值计算结果不存在：{self._display_path(resolved)}")
        try:
            markup = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise BuildError(
                f"无法读取数值计算结果：{self._display_path(resolved)}"
            ) from error
        source = self._display_path(resolved)
        document = self._parse(markup, source)
        container = self._find_result_container(document)
        if container is None:
            raise BuildError(f"无法从计算结果中提取 HTML 正文：{source}")

        selected = [
            node
            for node in container.children
            if not self._is_title_header(node)
        ]
        identifiers = self._collect_identifiers(selected, source)
        rewritten = self._rewrite_nodes(
            selected,
            identifiers=identifiers,
            prefix=prefix,
            source=source,
            shift_headings=True,
            image_alt_prefix=image_alt_prefix,
            image_counter=[0],
        )
        return str(join(self._render(node) for node in rewritten)).strip()

    def build_appendices(
        self,
        pages: Sequence[ComputationPage],
        orders: Mapping[str, Sequence[ComputationGroupLike]],
        *,
        plain_text: Callable[[Any], str],
    ) -> dict[Path, str]:
        """Build chapter-to-appendix markup for all configured computations."""

        if not orders:
            return {}
        pages_by_title: dict[str, Path] = {}
        for page in pages:
            if not page.blocks or page.blocks[0].get("t") != "Header":
                continue
            title = plain_text(page.blocks[0]["c"][2]).strip()
            if not title:
                continue
            qmd_path = self.quarto_project_dir / page.source_path
            pages_by_title[title] = qmd_path
            normalized = re.sub(r"^第\s*\d+\s*章\s*", "", title).strip()
            pages_by_title.setdefault(normalized, qmd_path)

        appendices: dict[Path, str] = {}
        result_count = 0
        for chapter_title, groups in orders.items():
            qmd_path = pages_by_title.get(chapter_title)
            if qmd_path is None or not qmd_path.is_file():
                raise BuildError(
                    f"找不到数值计算结果对应的网页章节：{chapter_title}"
                )
            articles = [
                self._build_case(group, group_index)
                for group_index, group in enumerate(groups, start=1)
            ]
            result_count += len(groups)
            appendix = element(
                "section",
                [
                    element(
                        "header",
                        [
                            element("p", text("COMPUTATIONAL NOTES")),
                            element("h2", text("计算实验")),
                        ],
                        attributes={"class": "computation-appendix-header"},
                    ),
                    join(articles),
                ],
                attributes={
                    "class": "computation-appendix",
                    "id": "computed-results",
                },
            )
            appendices[qmd_path] = str(appendix)

        if self.logger:
            self.logger(f"已插入 {result_count} 个计算实验")
        return appendices

    def append_to_site(
        self, appendices: Mapping[Path, str], rendered_site: Path
    ) -> None:
        """Insert generated appendices into their rendered Quarto pages."""

        rendered_root = rendered_site.resolve()
        for qmd_path, appendix in appendices.items():
            try:
                relative_html = qmd_path.resolve().relative_to(
                    self.quarto_project_dir
                ).with_suffix(".html")
            except ValueError as error:
                raise BuildError(
                    f"计算结果页面不在 Quarto 项目内：{qmd_path}"
                ) from error
            html_path = rendered_root / relative_html
            if not html_path.is_file():
                raise BuildError(f"找不到数值实验对应的已渲染网页：{relative_html}")
            try:
                markup = html_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                raise BuildError(f"无法读取已渲染网页：{relative_html}") from error
            locator = _StructureLocator(markup)
            locator.feed(markup)
            locator.close()
            if locator.main_close is None:
                raise BuildError(
                    f"网页缺少 quarto-document-content 主容器：{relative_html}"
                )
            position = locator.main_close
            updated = markup[:position] + appendix + "\n" + markup[position:]
            updated = self.append_toc(updated, appendix)
            try:
                html_path.write_text(updated, encoding="utf-8")
            except OSError as error:
                raise BuildError(f"无法写入已渲染网页：{relative_html}") from error

    def append_toc(self, markup: str, appendix: str) -> str:
        """Add one hierarchical computation entry to Quarto's page TOC."""

        case_parser = _CaseCollector()
        case_parser.feed(appendix)
        case_parser.close()
        links = [
            element(
                "li",
                element(
                    "a",
                    text(f"实验 {index:02d} · {title}"),
                    attributes={
                        "href": f"#{identifier}",
                        "class": "nav-link",
                        "data-scroll-target": f"#{identifier}",
                    },
                ),
            )
            for index, (identifier, title) in enumerate(
                case_parser.cases, start=1
            )
        ]
        toc_item = element(
            "li",
            [
                element(
                    "a",
                    text("计算实验"),
                    attributes={
                        "href": "#computed-results",
                        "class": "nav-link",
                        "data-scroll-target": "#computed-results",
                    },
                ),
                element("ul", links, attributes={"class": "collapse"}),
            ],
            attributes={"class": "computation-toc-item"},
        )
        locator = _StructureLocator(markup)
        locator.feed(markup)
        locator.close()
        if locator.toc_last_list_close is None:
            return markup
        position = locator.toc_last_list_close
        return markup[:position] + str(toc_item) + markup[position:]

    def _build_case(
        self, group: ComputationGroupLike, group_index: int
    ) -> Markup:
        results: list[Markup] = []
        for result_index, result_path in enumerate(group.result_paths, start=1):
            language = result_path.parent.name.lower()
            label = {
                "python": "Python · Jupyter",
                "r": "R · Quarto",
            }.get(language, result_path.parent.name)
            prefix = f"computation-{group_index:02d}-{result_index:02d}-"
            fragment = self.extract_fragment(
                result_path,
                prefix,
                image_alt_prefix=(
                    f"实验 {group_index:02d}「{group.title}」结果 {result_index}"
                ),
            )
            results.append(
                element(
                    "section",
                    [
                        element(
                            "div",
                            text(label),
                            attributes={"class": "computation-result-label"},
                        ),
                        element(
                            "div",
                            raw(fragment),
                            attributes={"class": "computation-result-body"},
                        ),
                    ],
                    attributes={"class": "computation-result"},
                )
            )
        return element(
            "article",
            [
                element(
                    "div",
                    [
                        element("span", text("实验")),
                        element("strong", text(f"{group_index:02d}")),
                    ],
                    attributes={"class": "computation-case-index"},
                ),
                element(
                    "h3",
                    text(group.title),
                    attributes={"class": "computation-case-title"},
                ),
                join(results),
            ],
            attributes={
                "class": "computation-case",
                "id": f"computation-case-{group_index:02d}",
            },
        )

    def _parse(self, markup: str, source: str) -> _Element:
        parser = _TreeParser(source)
        try:
            parser.feed(markup)
            parser.close()
            return parser.finish()
        except BuildError:
            raise
        except Exception as error:
            raise BuildError(f"无法解析计算结果 HTML：{source}") from error

    def _find_result_container(self, root: _Element) -> _Element | None:
        body: _Element | None = None
        stack = list(reversed(root.children))
        while stack:
            node = stack.pop()
            if not isinstance(node, _Element):
                continue
            if (
                node.tag == "main"
                and node.attribute("id") == "quarto-document-content"
            ):
                return node
            if node.tag == "body" and body is None:
                body = node
            stack.extend(reversed(node.children))
        return body

    @staticmethod
    def _is_title_header(node: _Node) -> bool:
        return (
            isinstance(node, _Element)
            and node.tag == "header"
            and node.attribute("id") == "title-block-header"
        )

    def _collect_identifiers(
        self, nodes: Iterable[_Node], source: str
    ) -> frozenset[str]:
        identifiers: set[str] = set()
        stack = list(nodes)
        while stack:
            node = stack.pop()
            if not isinstance(node, _Element):
                continue
            if node.tag in _REMOVED_ELEMENTS or self._is_title_header(node):
                continue
            identifier = node.attribute("id")
            if identifier is not None:
                if not identifier.strip():
                    raise BuildError(f"计算结果包含空 id：{source}")
                if identifier in identifiers:
                    raise BuildError(
                        f"计算结果包含重复 id {identifier!r}：{source}"
                    )
                identifiers.add(identifier)
            stack.extend(node.children)
        return frozenset(identifiers)

    def _rewrite_nodes(
        self,
        nodes: Iterable[_Node],
        *,
        identifiers: frozenset[str],
        prefix: str,
        source: str,
        shift_headings: bool,
        image_alt_prefix: str,
        image_counter: list[int],
    ) -> list[_Node]:
        if not _VALID_PREFIX.fullmatch(prefix):
            raise BuildError(f"计算结果 ID 前缀无效：{prefix!r}")
        rewritten: list[_Node] = []
        for node in nodes:
            if not isinstance(node, _Element):
                rewritten.append(node)
                continue
            if node.tag in _REMOVED_ELEMENTS or self._is_title_header(node):
                continue
            if node.tag in _FORBIDDEN_ELEMENTS:
                raise BuildError(
                    f"计算结果包含不允许的活动元素 <{node.tag}>："
                    f"{source}"
                )
            if node.tag in _DOCUMENT_ONLY_ELEMENTS:
                raise BuildError(
                    f"计算结果正文不应包含 <{node.tag}>：{source}"
                )
            tag = node.tag
            if shift_headings and re.fullmatch(r"h[1-6]", tag):
                tag = f"h{min(6, int(tag[1]) + 2)}"
            known_data_images: dict[str, GeneratedImageInfo] = {}
            if tag in {"img", "source"} or tag in _SVG_IMAGE_TAGS:
                known_data_images = self._validate_image_quality(node, source)
            attributes = self._rewrite_attributes(
                tag,
                node.attributes,
                identifiers=identifiers,
                prefix=prefix,
                source=source,
                known_data_images=known_data_images,
            )
            if tag == "img" and not any(
                name == "alt" for name, _value in attributes
            ):
                image_counter[0] += 1
                attributes.append(
                    (
                        "alt",
                        f"{image_alt_prefix}（图 {image_counter[0]}）",
                    )
                )
            children = self._rewrite_nodes(
                node.children,
                identifiers=identifiers,
                prefix=prefix,
                source=source,
                shift_headings=shift_headings,
                image_alt_prefix=image_alt_prefix,
                image_counter=image_counter,
            )
            rewritten.append(
                _Element(tag, attributes, children, node.self_closing)
            )
        return rewritten

    def _rewrite_attributes(
        self,
        tag: str,
        attributes: Iterable[tuple[str, str | None]],
        *,
        identifiers: frozenset[str],
        prefix: str,
        source: str,
        known_data_images: Mapping[str, GeneratedImageInfo],
    ) -> list[tuple[str, str | None]]:
        rewritten: list[tuple[str, str | None]] = []
        seen: set[str] = set()
        for raw_name, value in attributes:
            name = raw_name.lower()
            if name in seen:
                raise BuildError(
                    f"计算结果 <{tag}> 包含重复属性 {name!r}：{source}"
                )
            seen.add(name)
            if name.startswith("on"):
                raise BuildError(
                    f"计算结果包含不允许的事件属性 {name!r}：{source}"
                )
            if name in _FORBIDDEN_ATTRIBUTES:
                raise BuildError(
                    f"计算结果包含不允许的活动属性 {name!r}：{source}"
                )
            if value is None and (
                name in _RESOURCE_ATTRIBUTES.get(tag, frozenset())
                or name in {"background", "href", "xlink:href"}
            ):
                raise BuildError(
                    f"计算结果包含空资源属性 <{tag}> {name}：{source}"
                )
            updated = value
            if value is not None:
                if name == "id":
                    updated = prefix + value
                elif name in _SINGLE_IDREF_ATTRIBUTES:
                    updated = (
                        prefix + value if value in identifiers else value
                    )
                elif name in _MULTIPLE_IDREF_ATTRIBUTES:
                    updated = " ".join(
                        prefix + token if token in identifiers else token
                        for token in value.split()
                    )
                elif name in _FRAGMENT_ATTRIBUTES:
                    updated = self._rewrite_fragment_reference(
                        value, identifiers, prefix
                    )
                elif name in {"begin", "end"}:
                    updated = self._rewrite_smil_references(
                        value, identifiers, prefix
                    )
                updated = self._rewrite_css_fragments(
                    updated, identifiers, prefix
                )
                self._validate_attribute_resource(
                    tag,
                    name,
                    updated,
                    source,
                    known_data_images=known_data_images,
                )
            rewritten.append((name, updated))
        return rewritten

    @staticmethod
    def _rewrite_fragment_reference(
        value: str, identifiers: frozenset[str], prefix: str
    ) -> str:
        if value.startswith("#") and value[1:] in identifiers:
            return "#" + prefix + value[1:]
        return value

    @staticmethod
    def _rewrite_css_fragments(
        value: str, identifiers: frozenset[str], prefix: str
    ) -> str:
        def replace(match: re.Match[str]) -> str:
            identifier = match.group(2)
            if not identifier.startswith("#") or identifier[1:] not in identifiers:
                return match.group(0)
            quote = match.group(1)
            return f"url({quote}#{prefix}{identifier[1:]}{quote})"

        return _CSS_URL.sub(replace, value)

    @staticmethod
    def _rewrite_smil_references(
        value: str, identifiers: frozenset[str], prefix: str
    ) -> str:
        """Namespace ``element.event`` references in SVG animation timing."""

        updated = value
        for identifier in sorted(identifiers, key=len, reverse=True):
            updated = re.sub(
                rf"(?<![\w:.-]){re.escape(identifier)}(?=\.)",
                prefix + identifier,
                updated,
            )
        return updated

    def _validate_attribute_resource(
        self,
        tag: str,
        attribute: str,
        value: str,
        source: str,
        *,
        known_data_images: Mapping[str, GeneratedImageInfo],
    ) -> None:
        resource_attributes = _RESOURCE_ATTRIBUTES.get(tag, frozenset())
        is_svg_image = tag in _SVG_IMAGE_TAGS and attribute in {
            "href",
            "xlink:href",
        }
        is_svg_fragment_resource = (
            tag in _SVG_FRAGMENT_RESOURCE_TAGS
            and attribute in {"href", "xlink:href"}
        )
        for match in _CSS_URL.finditer(value):
            target = match.group(2).strip()
            self._validate_resource_target(
                target,
                source=f"{source} -> <{tag}> {attribute}",
                allow_fragment=True,
                known_data_images=known_data_images,
                enforce_raster_quality=True,
            )
        if attribute in resource_attributes:
            targets = (
                self._srcset_targets(value)
                if attribute == "srcset"
                else (value,)
            )
            for target in targets:
                self._validate_resource_target(
                    target,
                    source=f"{source} -> <{tag}> {attribute}",
                    allow_fragment=False,
                    known_data_images=known_data_images,
                )
        elif is_svg_image:
            self._validate_resource_target(
                value,
                source=f"{source} -> <{tag}> {attribute}",
                allow_fragment=True,
                known_data_images=known_data_images,
            )
        elif is_svg_fragment_resource:
            self._validate_local_fragment(
                value,
                source=f"{source} -> <{tag}> {attribute}",
            )
        elif tag in {"a", "area"} and attribute == "href":
            self._validate_navigation_target(value, source)
        elif attribute in {"href", "xlink:href"}:
            self._validate_local_fragment(
                value,
                source=f"{source} -> <{tag}> {attribute}",
            )
        elif attribute == "background":
            self._validate_resource_target(
                value,
                source=f"{source} -> <{tag}> {attribute}",
                allow_fragment=False,
                known_data_images=known_data_images,
            )

    def _validate_resource_target(
        self,
        target: str,
        *,
        source: str,
        allow_fragment: bool,
        known_data_images: Mapping[str, GeneratedImageInfo],
        enforce_raster_quality: bool = False,
    ) -> None:
        stripped = target.strip()
        if not stripped:
            raise BuildError(f"计算结果包含空资源地址：{source}")
        if stripped.startswith("#"):
            if allow_fragment:
                return
            raise BuildError(f"计算结果包含无效资源地址 {stripped!r}：{source}")
        parsed = urlsplit(stripped)
        if parsed.scheme.lower() == "data":
            image = known_data_images.get(stripped)
            if image is None:
                image = self._inspect_data_uri(stripped, source)
            if (
                enforce_raster_quality
                and not image.vector
            ):
                self._require_raster_quality(
                    image.width,
                    logical_width=None,
                    source=source,
                )
            return
        raise BuildError(
            "计算结果包含未嵌入或外部资源，请使用 embed-resources: true "
            f"重新渲染：{source} -> {stripped}"
        )

    @staticmethod
    def _validate_local_fragment(target: str, *, source: str) -> None:
        stripped = target.strip()
        if not stripped.startswith("#") or len(stripped) == 1:
            raise BuildError(
                "计算结果中的 SVG 引用必须指向当前片段："
                f"{source} -> {stripped!r}"
            )

    @staticmethod
    def _validate_navigation_target(target: str, source: str) -> None:
        stripped = target.strip()
        if not stripped or stripped.startswith("#"):
            return
        if stripped.startswith("//"):
            raise BuildError(f"计算结果包含协议相关链接：{source} -> {stripped}")
        scheme = urlsplit(stripped).scheme.lower()
        if scheme in {"http", "https", "mailto", "tel"}:
            return
        if scheme:
            raise BuildError(f"计算结果包含不安全链接：{source} -> {stripped}")
        raise BuildError(
            f"计算结果包含导入后会失效的相对链接：{source} -> {stripped}"
        )

    def _inspect_data_uri(
        self,
        target: str,
        source: str,
    ) -> GeneratedImageInfo:
        header, separator, encoded = target.partition(",")
        if not separator:
            raise BuildError(f"嵌入资源 data URI 无效：{source}")
        metadata = header[5:].split(";")
        mime = metadata[0].strip().lower()
        parameters = {part.strip().lower() for part in metadata[1:]}
        if not mime.startswith("image/") or "base64" not in parameters:
            raise BuildError(
                f"计算结果只允许 Base64 编码的嵌入图片：{source}"
            )
        return inspect_data_image(mime, encoded, source)

    def _validate_image_quality(
        self,
        node: _Element,
        source: str,
    ) -> dict[str, GeneratedImageInfo]:
        """Check raster density against the image's intended CSS width.

        Quarto writes an intrinsic ``width`` attribute for generated plots.
        Comparing physical pixels with that logical width correctly accepts a
        narrow 2x plot while still rejecting a blurry 1x plot.  Results without
        a logical width use the conservative absolute-width fallback.
        """

        declared_width = node.attribute("width")
        logical_width: int | None = None
        if declared_width is not None:
            normalized_width = declared_width.strip()
            if re.fullmatch(r"[1-9][0-9]*", normalized_width):
                logical_width = int(normalized_width)
            elif node.tag in {"img", "source"}:
                raise BuildError(
                    f"计算结果图片 width 必须是正整数：{source} -> "
                    f"{declared_width!r}"
                )

        src = node.attribute("src")
        if src is None and node.tag in _SVG_IMAGE_TAGS:
            src = node.attribute("href") or node.attribute("xlink:href")
        srcset = node.attribute("srcset")
        candidates = self._srcset_candidates(srcset) if srcset else ()
        targets = ([src] if src else []) + [
            candidate.target for candidate in candidates
        ]
        known_images: dict[str, GeneratedImageInfo] = {}
        for target in targets:
            if not target.strip().lower().startswith("data:"):
                continue
            if target not in known_images:
                known_images[target] = self._inspect_data_uri(
                    target,
                    f"{source} -> <{node.tag}> generated image",
                )
        if candidates:
            self._validate_srcset_quality(
                candidates,
                known_images,
                logical_width=logical_width,
                source=source,
            )
            return known_images
        if src is None or src not in known_images:
            return known_images
        image = known_images[src]
        if image.vector:
            return known_images
        self._require_raster_quality(
            image.width,
            logical_width=logical_width,
            source=source,
        )
        return known_images

    def _validate_srcset_quality(
        self,
        candidates: tuple[_SrcsetCandidate, ...],
        known_images: Mapping[str, GeneratedImageInfo],
        *,
        logical_width: int | None,
        source: str,
    ) -> None:
        embedded = [
            (candidate, known_images[candidate.target])
            for candidate in candidates
            if candidate.target in known_images
        ]
        if not embedded:
            return
        raster = [
            (candidate, image)
            for candidate, image in embedded
            if not image.vector
        ]
        if not raster:
            return

        descriptor_kind = candidates[0].descriptor_kind
        if descriptor_kind == "width":
            for candidate, image in raster:
                if image.width + 1e-9 < candidate.descriptor_value:
                    raise BuildError(
                        "计算结果 srcset 的实际像素宽度小于其 w 描述符："
                        f"{source}"
                    )
            available_width = max(
                min(float(image.width), candidate.descriptor_value)
                for candidate, image in raster
            )
        else:
            if logical_width is not None:
                for candidate, image in raster:
                    required_width = logical_width * candidate.descriptor_value
                    if image.width + 1e-9 < required_width:
                        raise BuildError(
                            "计算结果 srcset 的实际像素宽度小于其 x 描述符："
                            f"{source}"
                        )
            else:
                logical_fallback = (
                    self.minimum_raster_width / self.minimum_pixel_ratio
                )
                for candidate, image in raster:
                    required_width = (
                        logical_fallback * candidate.descriptor_value
                    )
                    if image.width + 1e-9 < required_width:
                        raise BuildError(
                            "计算结果 srcset 的位图候选低于无逻辑宽度"
                            f"图片的质量下限：{source}"
                        )
            available_width = max(
                float(image.width)
                for _candidate, image in raster
            )
        highest_descriptor = max(
            candidate.descriptor_value for candidate in candidates
        )
        if any(
            image.vector
            and candidate.descriptor_value == highest_descriptor
            for candidate, image in embedded
        ):
            return
        self._require_raster_quality(
            available_width,
            logical_width=logical_width,
            source=source,
        )

    def _require_raster_quality(
        self,
        available_width: float,
        *,
        logical_width: int | None,
        source: str,
    ) -> None:
        if logical_width is not None:
            actual_ratio = available_width / logical_width
            if actual_ratio + 1e-9 >= self.minimum_pixel_ratio:
                return
            raise BuildError(
                f"计算结果位图像素倍率仅 {actual_ratio:.2f}x，"
                f"未达到配置要求的 {self.minimum_pixel_ratio:g}x：{source}；"
                "请优先输出 SVG，或以更高分辨率重新生成 PNG/JPEG"
            )
        if available_width + 1e-9 < self.minimum_raster_width:
            raise BuildError(
                f"计算结果位图宽度仅 {available_width:g}px，"
                "未达到无逻辑宽度图片的配置要求 "
                f"{self.minimum_raster_width}px：{source}；"
                "请优先输出 SVG，或以更高分辨率重新生成 PNG/JPEG"
            )

    @staticmethod
    def _srcset_candidates(value: str) -> tuple[_SrcsetCandidate, ...]:
        """Parse and validate a conservative embedded-image ``srcset``."""

        candidates: list[_SrcsetCandidate] = []
        position = 0
        length = len(value)
        while position < length:
            while position < length and value[position] in " \t\r\n,":
                position += 1
            if position >= length:
                break
            start = position
            if value[position : position + 5].lower() == "data:":
                header_end = value.find(",", position)
                if header_end < 0:
                    raise BuildError("srcset 中的 data URI 缺少内容分隔符")
                position = header_end + 1
                while position < length and value[position] not in " \t\r\n,":
                    position += 1
            else:
                while position < length and value[position] not in " \t\r\n,":
                    position += 1
            target = value[start:position]
            descriptor_start = position
            while position < length and value[position] != ",":
                position += 1
            descriptor = value[descriptor_start:position].strip()
            if not descriptor:
                descriptor_kind = "density"
                descriptor_value = 1.0
            elif re.fullmatch(r"[1-9][0-9]*w", descriptor):
                descriptor_kind = "width"
                descriptor_value = float(descriptor[:-1])
            elif re.fullmatch(
                r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)x",
                descriptor,
            ):
                descriptor_kind = "density"
                descriptor_value = float(descriptor[:-1])
                if descriptor_value <= 0 or not math.isfinite(descriptor_value):
                    raise BuildError(f"srcset 描述符无效：{descriptor!r}")
            else:
                raise BuildError(f"srcset 描述符无效：{descriptor!r}")
            candidates.append(
                _SrcsetCandidate(
                    target=target,
                    descriptor_kind=descriptor_kind,
                    descriptor_value=descriptor_value,
                )
            )
            if position < length:
                position += 1
        if not candidates:
            raise BuildError("计算结果包含空 srcset")
        descriptor_kinds = {
            candidate.descriptor_kind for candidate in candidates
        }
        if len(descriptor_kinds) != 1:
            raise BuildError("srcset 不能混用 x 与 w 描述符")
        descriptor_values = [
            candidate.descriptor_value for candidate in candidates
        ]
        if len(set(descriptor_values)) != len(descriptor_values):
            raise BuildError("srcset 不能包含重复描述符")
        return tuple(candidates)

    @staticmethod
    def _srcset_targets(value: str) -> tuple[str, ...]:
        return tuple(
            candidate.target
            for candidate in ComputationImporter._srcset_candidates(value)
        )

    @staticmethod
    def _render(node: _Node) -> Markup:
        if isinstance(node, _Text):
            return raw(node.value)
        if isinstance(node, _Entity):
            return raw(node.value)
        if isinstance(node, _Comment):
            safe_comment = node.value.replace("--", "—")
            return raw(f"<!--{safe_comment}-->")
        if not isinstance(node, _Element):
            raise BuildError("无法渲染未知的 HTML 节点")
        attributes: list[str] = []
        for key, value in node.attributes:
            if value is None:
                attributes.append(key)
            else:
                attributes.append(
                    f'{key}="{html.escape(value, quote=True)}"'
                )
        opening = "<" + node.tag
        if attributes:
            opening += " " + " ".join(attributes)
        if node.self_closing and node.tag not in _VOID_ELEMENTS:
            return raw(opening + "/>")
        opening += ">"
        if node.tag in _VOID_ELEMENTS:
            return raw(opening)
        content = join(
            ComputationImporter._render(child) for child in node.children
        )
        return raw(f"{opening}{content}</{node.tag}>")

    def _display_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.project_root).as_posix()
        except ValueError:
            return str(path)
