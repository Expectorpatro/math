"""Deployment-aware validation for the rendered static site."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


RESOURCE_ATTRIBUTES = {
    "a": ("href",),
    "img": ("src", "srcset"),
    "script": ("src",),
    "link": ("href",),
    "source": ("src", "srcset"),
    "iframe": ("src",),
    "object": ("data",),
    "video": ("src", "poster"),
    "audio": ("src",),
}


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
        self.duplicate_identifiers: set[str] = set()
        self.resource_identifiers: set[str] = set()
        self.duplicate_resource_identifiers: set[str] = set()
        self.references: list[ResourceReference] = []

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        values = {key: value for key, value in attributes}
        identifier = values.get("id")
        if identifier:
            target = (
                self.resource_identifiers
                if tag in {"link", "style", "script"}
                else self.identifiers
            )
            duplicates = (
                self.duplicate_resource_identifiers
                if tag in {"link", "style", "script"}
                else self.duplicate_identifiers
            )
            if identifier in target:
                duplicates.add(identifier)
            target.add(identifier)
        for attribute in RESOURCE_ATTRIBUTES.get(tag, ()):
            value = values.get(attribute)
            if not value:
                continue
            if attribute == "srcset":
                for target in parse_srcset(value):
                    self.references.append(
                        ResourceReference(tag, attribute, target)
                    )
            else:
                self.references.append(ResourceReference(tag, attribute, value))


@dataclass(slots=True)
class ValidationReport:
    html_pages: int
    broken_links: list[dict[str, str]] = field(default_factory=list)
    broken_resources: list[dict[str, str]] = field(default_factory=list)
    duplicate_ids: dict[str, list[str]] = field(default_factory=dict)
    duplicate_resource_ids: dict[str, list[str]] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return bool(self.broken_links or self.broken_resources or self.duplicate_ids)

    def as_dict(self) -> dict[str, Any]:
        return {
            "html_pages": self.html_pages,
            "broken_links": self.broken_links,
            "broken_resources": self.broken_resources,
            "duplicate_ids": self.duplicate_ids,
            "duplicate_resource_ids": self.duplicate_resource_ids,
        }


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
            try:
                parsed = urlsplit(reference.target)
            except ValueError as error:
                issue = {
                    "page": page_name,
                    "target": reference.target,
                    "reason": f"URL 格式无效：{error}",
                }
                if reference.tag == "a":
                    issue["href"] = issue.pop("target")
                    report.broken_links.append(issue)
                else:
                    issue[reference.attribute] = issue.pop("target")
                    report.broken_resources.append(issue)
                continue
            if parsed.scheme or parsed.netloc or reference.target.startswith("//"):
                continue
            target_path = (
                (page.parent / unquote(parsed.path)).resolve()
                if parsed.path
                else page
            )
            try:
                target_path.relative_to(output_dir)
            except ValueError:
                issue = {
                    "page": page_name,
                    "target": reference.target,
                    "reason": "目标逃出发布目录",
                }
                if reference.tag == "a":
                    issue["href"] = issue.pop("target")
                    report.broken_links.append(issue)
                else:
                    issue[reference.attribute] = issue.pop("target")
                    report.broken_resources.append(issue)
                continue
            if target_path.is_dir():
                target_path = target_path / "index.html"
            target_page = pages.get(target_path)
            if not target_path.exists():
                issue = {
                    "page": page_name,
                    "target": reference.target,
                    "reason": "目标文件不在发布站点中",
                }
                if reference.tag == "a":
                    issue["href"] = issue.pop("target")
                    report.broken_links.append(issue)
                else:
                    issue[reference.attribute] = issue.pop("target")
                    report.broken_resources.append(issue)
                continue
            fragment = unquote(parsed.fragment)
            if fragment and target_page is not None and fragment not in target_page.identifiers:
                report.broken_links.append(
                    {
                        "page": page_name,
                        "href": reference.target,
                        "reason": "目标锚点不存在",
                    }
                )
    return report
