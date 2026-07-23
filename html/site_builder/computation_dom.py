"""Restricted HTML tree and structural locators for computation imports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any, Protocol

from .errors import BuildError

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
_REMOVED_ELEMENTS = frozenset({"style"})
_FORBIDDEN_ELEMENTS = frozenset(
    {
        "animate",
        "animatemotion",
        "animatetransform",
        "applet",
        "discard",
        "embed",
        "fencedframe",
        "foreignobject",
        "form",
        "frame",
        "frameset",
        "iframe",
        "object",
        "portal",
        "script",
        "set",
    }
)
_DOCUMENT_ONLY_ELEMENTS = frozenset({"base", "link", "meta", "title"})
_FORBIDDEN_ATTRIBUTES = frozenset(
    {
        "autoplay",
        "formaction",
        "ping",
        "srcdoc",
    }
)
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
_SVG_IMAGE_TAGS = frozenset({"image"})
_SVG_FRAGMENT_RESOURCE_TAGS = frozenset({"mpath", "textpath", "use"})
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


@dataclass(frozen=True, slots=True)
class _SrcsetCandidate:
    """One validated ``srcset`` candidate and its selection descriptor."""

    target: str
    descriptor_kind: str
    descriptor_value: float


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
        elif (
            tag.lower() == "h3"
            and self._case_id
            and "computation-case-title"
            in (values.get("class") or "").split()
        ):
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
