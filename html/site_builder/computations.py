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
from dataclasses import dataclass, field
import html
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any, Protocol
from urllib.parse import urlsplit

from .errors import BuildError
from .images import inspect_data_image
from .markup import Markup, element, join, raw, text


_VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_REMOVED_ELEMENTS = frozenset({"script", "style"})
_DOCUMENT_ONLY_ELEMENTS = frozenset({"base", "link", "meta", "title"})
_SINGLE_IDREF_ATTRIBUTES = frozenset(
    {
        "aria-activedescendant",
        "aria-details",
        "aria-errormessage",
        "commandfor",
        "data-anchor-id",
        "for",
        "form",
        "list",
        "popovertarget",
    }
)
_MULTIPLE_IDREF_ATTRIBUTES = frozenset(
    {
        "aria-controls",
        "aria-describedby",
        "aria-flowto",
        "aria-labelledby",
        "aria-owns",
        "headers",
        "itemref",
    }
)
_FRAGMENT_ATTRIBUTES = frozenset(
    {
        "data-bs-target",
        "data-scroll-target",
        "data-target",
        "href",
        "xlink:href",
    }
)
_RESOURCE_ATTRIBUTES: Mapping[str, frozenset[str]] = {
    "audio": frozenset({"src"}),
    "embed": frozenset({"src"}),
    "iframe": frozenset({"src"}),
    "img": frozenset({"src", "srcset"}),
    "input": frozenset({"src"}),
    "object": frozenset({"data"}),
    "source": frozenset({"src", "srcset"}),
    "track": frozenset({"src"}),
    "video": frozenset({"poster", "src"}),
}
_SVG_RESOURCE_TAGS = frozenset({"image", "use"})
_CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
_VALID_PREFIX = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")


class ComputationPage(Protocol):
    """The page fields required by :class:`ComputationImporter`."""

    source_path: Path
    blocks: list[dict[str, Any]]


class ComputationGroupLike(Protocol):
    """The computation-order fields required by the importer."""

    title: str
    result_paths: Sequence[Path]


@dataclass(slots=True)
class _Node:
    """Base type for the intentionally small internal HTML tree."""


@dataclass(slots=True)
class _Text(_Node):
    value: str


@dataclass(slots=True)
class _Entity(_Node):
    value: str


@dataclass(slots=True)
class _Comment(_Node):
    value: str


@dataclass(slots=True)
class _Element(_Node):
    tag: str
    attributes: list[tuple[str, str | None]]
    children: list[_Node] = field(default_factory=list)
    self_closing: bool = False

    def attribute(self, name: str) -> str | None:
        for key, value in self.attributes:
            if key == name:
                return value
        return None


class _TreeParser(HTMLParser):
    """Parse generated HTML into a small tree while preserving mixed text."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.root = _Element("__root__", [])
        self._stack = [self.root]

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        normalized = tag.lower()
        node = _Element(normalized, list(attributes))
        self._stack[-1].children.append(node)
        if normalized not in _VOID_ELEMENTS:
            self._stack.append(node)

    def handle_startendtag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        self._stack[-1].children.append(
            _Element(tag.lower(), list(attributes), self_closing=True)
        )

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in _VOID_ELEMENTS:
            return
        if len(self._stack) == 1:
            raise BuildError(f"HTML 出现多余的 </{normalized}>：{self.source}")
        if self._stack[-1].tag != normalized:
            open_tag = self._stack[-1].tag
            raise BuildError(
                f"HTML 标签嵌套无效（<{open_tag}> 后遇到 </{normalized}>）："
                f"{self.source}"
            )
        self._stack.pop()

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(_Text(data))

    def handle_entityref(self, name: str) -> None:
        self._stack[-1].children.append(_Entity(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self._stack[-1].children.append(_Entity(f"&#{name};"))

    def handle_comment(self, data: str) -> None:
        self._stack[-1].children.append(_Comment(data))

    def finish(self) -> _Element:
        if len(self._stack) != 1:
            unclosed = " > ".join(node.tag for node in self._stack[1:])
            raise BuildError(f"HTML 存在未闭合标签（{unclosed}）：{self.source}")
        return self.root


class _StructureLocator(HTMLParser):
    """Locate safe insertion offsets without rewriting a rendered page."""

    def __init__(self, markup: str) -> None:
        super().__init__(convert_charrefs=True)
        self._line_offsets = [0]
        self._line_offsets.extend(
            match.end() for match in re.finditer(r"\n", markup)
        )
        self._target_main_depth = 0
        self.main_close: int | None = None
        self._toc_depth = 0
        self.toc_last_list_close: int | None = None

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_offsets[line - 1] + column

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attributes)
        normalized = tag.lower()
        if normalized == "main":
            if self._target_main_depth:
                self._target_main_depth += 1
            elif values.get("id") == "quarto-document-content":
                self._target_main_depth = 1
        if normalized == "nav":
            if self._toc_depth:
                self._toc_depth += 1
            elif values.get("id") == "TOC":
                self._toc_depth = 1

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if self._toc_depth and normalized == "ul":
            self.toc_last_list_close = self._offset()
        if self._target_main_depth and normalized == "main":
            self._target_main_depth -= 1
            if self._target_main_depth == 0 and self.main_close is None:
                self.main_close = self._offset()
        if self._toc_depth and normalized == "nav":
            self._toc_depth -= 1


class _CaseCollector(HTMLParser):
    """Collect generated computation case IDs and headings for the TOC."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cases: list[tuple[str, str]] = []
        self._case_id: str | None = None
        self._in_heading = False
        self._heading_parts: list[str] = []

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attributes)
        if tag.lower() == "article":
            identifier = values.get("id")
            if identifier and identifier.startswith("computation-case-"):
                self._case_id = identifier
        elif tag.lower() == "h3" and self._case_id:
            self._in_heading = True
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized == "h3" and self._in_heading and self._case_id:
            title = " ".join("".join(self._heading_parts).split())
            self.cases.append((self._case_id, title))
            self._in_heading = False
        elif normalized == "article":
            self._case_id = None


class ComputationImporter:
    """Validate and import standalone computation-result HTML documents."""

    def __init__(
        self,
        *,
        project_root: Path,
        quarto_project_dir: Path,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.quarto_project_dir = quarto_project_dir.resolve()
        self.logger = logger

    def prefix_identifiers(
        self,
        fragment: str,
        prefix: str,
        *,
        source: str = "计算结果片段",
    ) -> str:
        """Namespace every ID and in-fragment reference in ``fragment``."""

        if not _VALID_PREFIX.fullmatch(prefix):
            raise BuildError(f"计算结果 ID 前缀无效：{prefix!r}")
        root = self._parse(fragment, source)
        identifiers = self._collect_identifiers(root.children, source)
        rewritten = self._rewrite_nodes(
            root.children,
            identifiers=identifiers,
            prefix=prefix,
            source=source,
            shift_headings=False,
            image_alt_prefix="计算结果图",
            image_counter=[0],
        )
        return str(join(self._render(node) for node in rewritten))

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
                element("h3", text(group.title)),
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
            if node.tag in _DOCUMENT_ONLY_ELEMENTS:
                raise BuildError(
                    f"计算结果正文不应包含 <{node.tag}>：{source}"
                )
            tag = node.tag
            if shift_headings and re.fullmatch(r"h[1-6]", tag):
                tag = f"h{min(6, int(tag[1]) + 2)}"
            attributes = self._rewrite_attributes(
                tag,
                node.attributes,
                identifiers=identifiers,
                prefix=prefix,
                source=source,
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
                    tag, name, updated, source
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
        self, tag: str, attribute: str, value: str, source: str
    ) -> None:
        resource_attributes = _RESOURCE_ATTRIBUTES.get(tag, frozenset())
        is_svg_resource = tag in _SVG_RESOURCE_TAGS and attribute in {
            "href",
            "xlink:href",
        }
        if attribute == "style":
            for match in _CSS_URL.finditer(value):
                target = match.group(2).strip()
                self._validate_resource_target(
                    target,
                    source=f"{source} -> <{tag}> style",
                    allow_fragment=True,
                )
        elif attribute in resource_attributes:
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
                )
        elif is_svg_resource:
            self._validate_resource_target(
                value,
                source=f"{source} -> <{tag}> {attribute}",
                allow_fragment=True,
            )
        elif tag == "a" and attribute == "href":
            self._validate_navigation_target(value, source)
        elif tag == "form" and attribute == "action":
            self._validate_navigation_target(value, source)

    def _validate_resource_target(
        self, target: str, *, source: str, allow_fragment: bool
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
            self._inspect_data_uri(stripped, source)
            return
        raise BuildError(
            "计算结果包含未嵌入或外部资源，请使用 embed-resources: true "
            f"重新渲染：{source} -> {stripped}"
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

    def _inspect_data_uri(self, target: str, source: str) -> None:
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
        inspect_data_image(mime, encoded, source)

    @staticmethod
    def _srcset_targets(value: str) -> tuple[str, ...]:
        """Parse the URL portion of a conservative, embedded-image srcset."""

        targets: list[str] = []
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
            targets.append(value[start:position])
            while position < length and value[position] != ",":
                position += 1
            if position < length:
                position += 1
        if not targets:
            raise BuildError("计算结果包含空 srcset")
        return tuple(targets)

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
