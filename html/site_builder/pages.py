"""Plan book pages and rewrite cross-page Pandoc targets."""

from __future__ import annotations

import hashlib
from pathlib import Path
import posixpath
import re
from typing import Any
from urllib.parse import urlsplit

from .models import QuartoPage
from .pandoc_transform import BookTransformer, ast_plain_text, attr_parts, node_identifier


PAGE_SLUGS = {
    "前言": "preface",
    "线性空间": "linear-space",
    "矩阵": "matrix",
    "度量空间": "metric-space",
    "微积分": "calculus",
    "概率测度": "probability-measure",
    "概率初步": "probability-basics",
    "渐进理论初步": "asymptotic-theory",
    "凸集": "convex-sets",
    "不等式": "inequalities",
    "统计初步": "statistics-basics",
    "点估计理论": "point-estimation",
    "假设检验理论": "hypothesis-testing",
    "贝叶斯统计": "bayesian-statistics",
    "统计计算方法": "statistical-computing",
    "线性模型": "linear-models",
    "多元统计": "multivariate-statistics",
    "时间序列分析": "time-series",
    "机器学习": "machine-learning",
    "因果推断": "causal-inference",
    "附录": "appendix",
    "后记": "epilogue",
    "中英术语表": "glossary",
}


def shift_header_levels(value: Any, amount: int) -> Any:
    if isinstance(value, list):
        return [shift_header_levels(item, amount) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("t") == "Header":
        value["c"][0] = max(1, value["c"][0] + amount)
    if "c" in value:
        value["c"] = shift_header_levels(value["c"], amount)
    return value


def quarto_page_slug(title: str, identifier: str, page_number: int) -> str:
    normalized = re.sub(r"^第\s*\d+\s*章\s*", "", title).strip()
    if identifier == "glossary":
        return "glossary"
    letter_match = re.fullmatch(r"glossary-letter-([A-Z])", identifier)
    if letter_match:
        return f"glossary-{letter_match.group(1).lower()}"
    configured = PAGE_SLUGS.get(normalized)
    if configured:
        return configured
    # Unknown chapters must not have their public URL changed merely because a
    # new page was inserted earlier in the book.  Keep the readable registry
    # for known chapters and use a deterministic content identity as fallback.
    identity = (
        f"{normalized}\0{identifier}"
        if normalized or identifier
        else f"page-{page_number:03d}"
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
    return f"page-{digest}"


def split_quarto_pages(
    document: dict[str, Any], transformer: BookTransformer
) -> list[QuartoPage]:
    pages: list[QuartoPage] = []
    current_blocks: list[dict[str, Any]] = []
    current_part: str | None = None
    page_part: str | None = None
    page_number = 0

    def finish_page() -> None:
        nonlocal current_blocks, page_number
        if not current_blocks:
            return
        page_number += 1
        page_identifier = node_identifier(current_blocks[0])
        title = ast_plain_text(current_blocks[0]["c"][2]).strip()
        page_slug = quarto_page_slug(title, page_identifier, page_number)
        shifted = shift_header_levels(
            current_blocks,
            1 - transformer.chapter_level,
        )
        pages.append(
            QuartoPage(
                source_path=Path("chapters") / f"{page_slug}.qmd",
                blocks=shifted,
                part=page_part,
                sidebar_visible=not page_identifier.startswith(
                    "glossary-letter-"
                ),
            )
        )
        current_blocks = []

    for block in document["blocks"]:
        if block.get("t") == "Header":
            level, attribute, inlines = block["c"]
            _, classes, _ = attr_parts(attribute)
            if transformer.has_parts and level == transformer.part_level:
                finish_page()
                current_part = ast_plain_text(inlines).strip()
                continue
            if level == transformer.chapter_level:
                finish_page()
                page_part = None if "unnumbered" in classes else current_part
                current_blocks = [block]
                continue
        if current_blocks:
            current_blocks.append(block)
    finish_page()
    return pages


def ast_header(
    level: int,
    identifier: str,
    classes: list[str],
    text: str,
) -> dict[str, Any]:
    return {
        "t": "Header",
        "c": [
            level,
            [identifier, classes, []],
            [{"t": "Str", "c": text}],
        ],
    }


def empty_div(identifier: str) -> dict[str, Any]:
    return {
        "t": "Div",
        "c": [[identifier, [], []], []],
    }


def page_title(page: QuartoPage) -> str:
    for block in page.blocks:
        if block.get("t") == "Header":
            return ast_plain_text(block["c"][2]).strip()
    return ""


def add_reference_page(pages: list[QuartoPage]) -> None:
    references_page = QuartoPage(
        source_path=Path("references.qmd"),
        blocks=[
            ast_header(1, "references", ["unnumbered"], "参考文献"),
            empty_div("refs"),
        ],
        part=None,
    )
    insertion_index = len(pages)
    for index, page in enumerate(pages):
        title = page_title(page)
        first_identifier = node_identifier(page.blocks[0]) if page.blocks else ""
        if title == "后记" or first_identifier == "glossary":
            insertion_index = index
            break
    pages.insert(insertion_index, references_page)


def collect_identifiers(value: Any, result: set[str]) -> None:
    if isinstance(value, list):
        for item in value:
            collect_identifiers(item, result)
        return
    if not isinstance(value, dict):
        return
    if value.get("t") is None:
        for item in value.values():
            collect_identifiers(item, result)
        return
    identifier = node_identifier(value)
    if identifier:
        result.add(identifier)
    if "c" in value:
        collect_identifiers(value["c"], result)


def safe_quarto_identifier(identifier: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", identifier).strip("-")
    if not safe or not safe[0].isalpha():
        safe = f"id-{safe}"
    if identifier.startswith("alg:"):
        safe = f"source-{safe}"
    if safe in {"title", "toc-title"}:
        safe = f"source-{safe}"
    if safe != identifier:
        digest = hashlib.sha1(identifier.encode("utf-8")).hexdigest()[:8]
        safe = f"{safe}-{digest}"
    return safe


def set_node_identifier(node: dict[str, Any], identifier: str) -> None:
    node_type = node.get("t")
    content = node.get("c")
    if node_type in {"Div", "Span", "CodeBlock", "Code", "Link", "Image"}:
        content[0][0] = identifier
    elif node_type == "Header":
        content[1][0] = identifier
    elif node_type in {"Table", "Figure"}:
        content[0][0] = identifier


def sanitize_quarto_identifiers(document: dict[str, Any]) -> None:
    automatic_header = 0

    def assign_header_identifiers(value: Any) -> None:
        nonlocal automatic_header
        if isinstance(value, list):
            for item in value:
                assign_header_identifiers(item)
            return
        if not isinstance(value, dict):
            return
        if value.get("t") is None:
            for item in value.values():
                assign_header_identifiers(item)
            return
        if value.get("t") == "Header" and not node_identifier(value):
            automatic_header += 1
            set_node_identifier(
                value,
                f"section-auto-{automatic_header:04d}",
            )
        if "c" in value:
            assign_header_identifiers(value["c"])

    assign_header_identifiers(document)
    identifiers: set[str] = set()
    collect_identifiers(document, identifiers)
    mapping = {
        identifier: safe_quarto_identifier(identifier)
        for identifier in identifiers
    }

    def rewrite(value: Any) -> Any:
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if not isinstance(value, dict):
            return value
        if value.get("t") is None:
            return {key: rewrite(item) for key, item in value.items()}
        identifier = node_identifier(value)
        if identifier:
            set_node_identifier(value, mapping[identifier])
        if value.get("t") == "Link":
            target = value["c"][2][0]
            if target.startswith("#") and target[1:] in mapping:
                value["c"][2][0] = f"#{mapping[target[1:]]}"
        if "c" in value:
            value["c"] = rewrite(value["c"])
        return value

    rewrite(document)


def rewrite_quarto_targets(
    value: Any,
    current_page: Path,
    labels_to_pages: dict[str, Path],
) -> Any:
    if isinstance(value, list):
        return [
            rewrite_quarto_targets(item, current_page, labels_to_pages)
            for item in value
        ]
    if not isinstance(value, dict):
        return value

    if value.get("t") == "Link":
        target = value["c"][2][0]
        if target.startswith("#"):
            identifier = target[1:]
            target_page = labels_to_pages.get(identifier)
            if target_page is not None and target_page != current_page:
                relative = posixpath.relpath(
                    target_page.as_posix(),
                    start=current_page.parent.as_posix(),
                )
                value["c"][2][0] = f"{relative}#{identifier}"
    elif value.get("t") == "Image":
        target = value["c"][2][0]
        if target and not urlsplit(target).scheme:
            relative = posixpath.relpath(
                target,
                start=current_page.parent.as_posix(),
            )
            value["c"][2][0] = relative

    if "c" in value:
        value["c"] = rewrite_quarto_targets(
            value["c"], current_page, labels_to_pages
        )
    return value
