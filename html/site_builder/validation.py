"""Deployment-aware validation for the rendered static site."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


RESOURCE_ATTRIBUTES = {
    "a": ("href",),
    "area": ("href",),
    "audio": ("src",),
    "embed": ("src",),
    "feimage": ("href", "xlink:href"),
    "iframe": ("src",),
    "image": ("href", "xlink:href"),
    "img": ("src", "srcset"),
    "input": ("src",),
    "link": ("href", "imagesrcset"),
    "object": ("data",),
    "script": ("src",),
    "source": ("src", "srcset"),
    "track": ("src",),
    "use": ("href", "xlink:href"),
    "video": ("src", "poster"),
}
NAVIGATION_TAGS = frozenset({"a", "area"})
RESOURCE_ID_TAGS = frozenset({"link", "script", "style"})
SRCSET_ATTRIBUTES = frozenset({"imagesrcset", "srcset"})


def parse_srcset(value: str) -> list[str]:
    """Return URL tokens from ``srcset`` without splitting data-URI commas."""

    targets: list[str] = []
    position = 0
    length = len(value)
    while position < length:
        while position < length and (value[position].isspace() or value[position] == ","):
            position += 1
        if position >= length:
            break
        if value.startswith("data:", position):
            # A data URL may contain arbitrary commas. Its URL token ends at
            # whitespace; validation ignores the data scheme, so no decoding
            # is needed here.
            while position < length and not value[position].isspace():
                position += 1
            while position < length and value[position] != ",":
                position += 1
            continue
        start = position
        while (
            position < length
            and not value[position].isspace()
            and value[position] != ","
        ):
            position += 1
        if position > start:
            targets.append(value[start:position])
        while position < length and value[position] != ",":
            position += 1
    return targets


def _skip_css_comment(source: str, position: int) -> int:
    end = source.find("*/", position + 2)
    return len(source) if end < 0 else end + 2


def _skip_css_string(source: str, position: int) -> int:
    quote = source[position]
    position += 1
    while position < len(source):
        if source[position] == "\\":
            position += 2
            continue
        if source[position] == quote:
            return position + 1
        position += 1
    return len(source)


def parse_css_urls(source: str) -> list[str]:
    """Extract ``url(...)`` targets while ignoring comments and CSS strings."""

    targets: list[str] = []
    position = 0
    lowered = source.casefold()
    while position < len(source):
        if source.startswith("/*", position):
            position = _skip_css_comment(source, position)
            continue
        if source[position] in {'"', "'"}:
            position = _skip_css_string(source, position)
            continue
        if not lowered.startswith("url", position):
            position += 1
            continue
        if position and (
            source[position - 1].isalnum() or source[position - 1] in "_-"
        ):
            position += 1
            continue
        cursor = position + 3
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor >= len(source) or source[cursor] != "(":
            position += 1
            continue
        cursor += 1
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor < len(source) and source[cursor] in {'"', "'"}:
            quote = source[cursor]
            cursor += 1
            start = cursor
            while cursor < len(source):
                if source[cursor] == "\\":
                    cursor += 2
                    continue
                if source[cursor] == quote:
                    break
                cursor += 1
            target = source[start:cursor]
            cursor = min(cursor + 1, len(source))
            while cursor < len(source) and source[cursor].isspace():
                cursor += 1
            if cursor < len(source) and source[cursor] == ")":
                cursor += 1
        else:
            start = cursor
            while cursor < len(source) and source[cursor] != ")":
                cursor += 1
            target = source[start:cursor].strip()
            cursor = min(cursor + 1, len(source))
        if target and not target.casefold().startswith("var("):
            targets.append(target)
        position = cursor
    return targets


def parse_css_imports(source: str) -> list[str]:
    """Extract quoted ``@import`` targets outside comments and strings."""

    targets: list[str] = []
    position = 0
    lowered = source.casefold()
    while position < len(source):
        if source.startswith("/*", position):
            position = _skip_css_comment(source, position)
            continue
        if source[position] in {'"', "'"}:
            position = _skip_css_string(source, position)
            continue
        if not lowered.startswith("@import", position):
            position += 1
            continue
        end = position + len("@import")
        if end < len(source) and (
            source[end].isalnum() or source[end] in "_-"
        ):
            position += 1
            continue
        cursor = end
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor >= len(source) or source[cursor] not in {'"', "'"}:
            # url(...) imports are already handled by parse_css_urls().
            position = cursor
            continue
        quote = source[cursor]
        cursor += 1
        start = cursor
        while cursor < len(source):
            if source[cursor] == "\\":
                cursor += 2
                continue
            if source[cursor] == quote:
                break
            cursor += 1
        target = source[start:cursor]
        if target:
            targets.append(target)
        position = min(cursor + 1, len(source))
    return targets


def parse_css_references(source: str) -> list[str]:
    """Return local-or-external targets expressed by CSS URL constructs."""

    targets = parse_css_urls(source)
    # Quoted @import targets do not use url(...), so collect them separately.
    targets.extend(parse_css_imports(source))
    return targets


@dataclass(frozen=True, slots=True)
class ResourceReference:
    tag: str
    attribute: str
    target: str


class PageCollector(HTMLParser):
    """Collect fragment targets and deployable resources from one page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.identifiers: set[str] = set()
        self.all_identifiers: set[str] = set()
        self.duplicate_identifiers: set[str] = set()
        self.resource_identifiers: set[str] = set()
        self.duplicate_resource_identifiers: set[str] = set()
        self.references: list[ResourceReference] = []
        self._identifier_is_resource: dict[str, bool] = {}
        self._style_fragments: list[list[str]] = []

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        values = {key: value for key, value in attributes}
        identifier = values.get("id")
        if identifier:
            is_resource = tag in RESOURCE_ID_TAGS
            previous_kind = self._identifier_is_resource.get(identifier)
            if previous_kind is not None:
                if is_resource and previous_kind:
                    self.duplicate_resource_identifiers.add(identifier)
                else:
                    self.duplicate_identifiers.add(identifier)
            else:
                self._identifier_is_resource[identifier] = is_resource
            self.all_identifiers.add(identifier)
            if is_resource:
                self.resource_identifiers.add(identifier)
            else:
                self.identifiers.add(identifier)
        for attribute in RESOURCE_ATTRIBUTES.get(tag, ()):
            value = values.get(attribute)
            if not value:
                continue
            if attribute in SRCSET_ATTRIBUTES:
                for target in parse_srcset(value):
                    self.references.append(
                        ResourceReference(tag, attribute, target)
                    )
            else:
                self.references.append(ResourceReference(tag, attribute, value))
        style = values.get("style")
        if style:
            self.references.extend(
                ResourceReference(tag, "style", target)
                for target in parse_css_references(style)
            )
        if tag == "style":
            self._style_fragments.append([])

    def handle_data(self, data: str) -> None:
        if self._style_fragments:
            self._style_fragments[-1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "style" or not self._style_fragments:
            return
        source = "".join(self._style_fragments.pop())
        self.references.extend(
            ResourceReference("style", "text", target)
            for target in parse_css_references(source)
        )


@dataclass(slots=True)
class ValidationReport:
    html_pages: int
    broken_links: list[dict[str, str]] = field(default_factory=list)
    broken_resources: list[dict[str, str]] = field(default_factory=list)
    duplicate_ids: dict[str, list[str]] = field(default_factory=dict)
    duplicate_resource_ids: dict[str, list[str]] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return bool(
            self.broken_links
            or self.broken_resources
            or self.duplicate_ids
            or self.duplicate_resource_ids
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "html_pages": self.html_pages,
            "broken_links": self.broken_links,
            "broken_resources": self.broken_resources,
            "duplicate_ids": self.duplicate_ids,
            "duplicate_resource_ids": self.duplicate_resource_ids,
        }


def _append_issue(
    report: ValidationReport,
    *,
    owner_name: str,
    reference: ResourceReference,
    reason: str,
) -> None:
    issue = {"page": owner_name, "reason": reason}
    if reference.tag in NAVIGATION_TAGS:
        issue["href"] = reference.target
        report.broken_links.append(issue)
    else:
        issue[reference.attribute] = reference.target
        report.broken_resources.append(issue)


def _validate_reference(
    *,
    owner: Path,
    owner_name: str,
    reference: ResourceReference,
    output_dir: Path,
    pages: dict[Path, PageCollector],
    report: ValidationReport,
) -> None:
    try:
        parsed = urlsplit(reference.target)
    except ValueError as error:
        _append_issue(
            report,
            owner_name=owner_name,
            reference=reference,
            reason=f"URL 格式无效：{error}",
        )
        return
    if parsed.scheme or parsed.netloc or reference.target.startswith("//"):
        return
    target_path = (
        (owner.parent / unquote(parsed.path)).resolve() if parsed.path else owner
    )
    try:
        target_path.relative_to(output_dir)
    except ValueError:
        _append_issue(
            report,
            owner_name=owner_name,
            reference=reference,
            reason="目标逃出发布目录",
        )
        return
    if target_path.is_dir():
        target_path = target_path / "index.html"
    target_page = pages.get(target_path)
    if not target_path.exists():
        _append_issue(
            report,
            owner_name=owner_name,
            reference=reference,
            reason="目标文件不在发布站点中",
        )
        return
    fragment = unquote(parsed.fragment)
    if (
        fragment
        and target_page is not None
        and fragment not in target_page.all_identifiers
    ):
        _append_issue(
            report,
            owner_name=owner_name,
            reference=reference,
            reason="目标锚点不存在",
        )


def validate_site(output_dir: Path) -> ValidationReport:
    """Validate only files that will be present in the published directory."""

    output_dir = output_dir.resolve()
    pages: dict[Path, PageCollector] = {}
    for path in sorted(output_dir.rglob("*.html")):
        collector = PageCollector()
        collector.feed(path.read_text(encoding="utf-8"))
        pages[path.resolve()] = collector

    report = ValidationReport(html_pages=len(pages))
    for page, collector in pages.items():
        page_name = page.relative_to(output_dir).as_posix()
        if collector.duplicate_identifiers:
            report.duplicate_ids[page_name] = sorted(
                collector.duplicate_identifiers
            )
        if collector.duplicate_resource_identifiers:
            report.duplicate_resource_ids[page_name] = sorted(
                collector.duplicate_resource_identifiers
            )
        for reference in collector.references:
            _validate_reference(
                owner=page,
                owner_name=page_name,
                reference=reference,
                output_dir=output_dir,
                pages=pages,
                report=report,
            )

    for stylesheet in sorted(output_dir.rglob("*.css")):
        stylesheet = stylesheet.resolve()
        stylesheet_name = stylesheet.relative_to(output_dir).as_posix()
        source = stylesheet.read_text(encoding="utf-8")
        for target in parse_css_references(source):
            _validate_reference(
                owner=stylesheet,
                owner_name=stylesheet_name,
                reference=ResourceReference("css", "url", target),
                output_dir=output_dir,
                pages=pages,
                report=report,
            )
    return report
