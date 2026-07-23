"""Pandoc AST transformation for the staged LaTeX textbook.

This module owns semantic conversion only: it translates Pandoc nodes into the
book's theorem, proof, glossary, algorithm, table, and cross-reference model.
Filesystem staging and final site publication remain separate services.
"""

from __future__ import annotations

import base64
from collections import Counter
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable

from .commands import CommandRunner
from .config import BuildConfig
from .constants import (
    ALGORITHM_COMMAND_PREFIX,
    ALGORITHM_TITLE_END_PREFIX,
    ALGORITHM_TITLE_START_PREFIX,
    BLOCK_TYPES,
    DENSITY_PLOT_MARKER_PREFIX,
    TABLE_MARKER_PREFIX,
    TITLE_MARKER_PREFIX,
)
from .errors import BuildError
from .models import LatexTable, Term, TheoremSpec
from .pandoc_ast import (
    attr_dict,
    attr_parts,
    make_attr,
    node_identifier,
    remove_labels_from_inlines,
    remove_theorem_labels,
    replace_first_strong,
    rewrite_title_markers,
    rewrite_todo_markers,
    scoped_term_key,
    space_inline,
    span_inline,
    str_inline,
    trim_inline_spaces,
    unwrap_emphasis,
)
from .pandoc_tables import (
    latex_to_html_fragment,
    latex_to_plain,
    render_latex_table,
)
from .pandoc_glossary import GlossaryAppenderMixin


def fail(message: str) -> None:
    raise BuildError(message)


def remove_pandoc_proof_prefix(blocks: list[dict[str, Any]]) -> None:
    for block in blocks:
        if block.get("t") not in {"Para", "Plain"}:
            continue
        inlines = block["c"]
        if not inlines:
            return
        first = inlines[0]
        if first.get("t") == "Emph":
            prefix = ast_plain_text(first).strip()
            if prefix in {"Proof.", "Proof", "证明.", "证明"}:
                inlines.pop(0)
                while inlines and inlines[0].get("t") in {"Space", "SoftBreak"}:
                    inlines.pop(0)
        return


def extract_algorithm_caption(
    blocks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    for block_index, block in enumerate(blocks):
        if block.get("t") not in {"Para", "Plain"}:
            continue
        inlines = block["c"]
        if len(inlines) != 1 or inlines[0].get("t") != "Strong":
            continue
        title = list(inlines[0]["c"])
        if (
            len(title) < 2
            or title[0].get("t") != "Str"
            or title[-1].get("t") != "Str"
            or not str(title[0].get("c", "")).startswith(
                ALGORITHM_TITLE_START_PREFIX
            )
            or not str(title[-1].get("c", "")).startswith(
                ALGORITHM_TITLE_END_PREFIX
            )
        ):
            continue
        del blocks[block_index]
        return blocks, trim_inline_spaces(title[1:-1])
    return blocks, []


def extract_algorithm_labels(
    blocks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    labels: list[str] = []
    retained: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("t") == "Div":
            identifier, classes, attributes = attr_parts(block["c"][0])
            if (
                identifier
                and not classes
                and not attributes
                and not block["c"][1]
            ):
                labels.append(identifier)
                continue
        retained.append(block)
    return retained, labels


def remove_algorithm_command_marker(
    blocks: list[dict[str, Any]],
) -> str:
    for block in blocks:
        if block.get("t") not in {"Para", "Plain"}:
            continue
        inlines = block["c"]
        if not inlines or inlines[0].get("t") != "Strong":
            return "state"
        marker = ast_plain_text(inlines[0]).strip()
        if not marker.startswith(ALGORITHM_COMMAND_PREFIX):
            return "state"
        kind = marker[len(ALGORITHM_COMMAND_PREFIX) :].lower()
        inlines.pop(0)
        while inlines and inlines[0].get("t") in {
            "Space",
            "SoftBreak",
        }:
            inlines.pop(0)
        return kind
    return "state"




class BookTransformer(GlossaryAppenderMixin):
    def __init__(
        self,
        theorem_specs: dict[str, TheoremSpec],
        glossary: dict[str, Term],
        glossary_catalog: list[Term],
        latex_tables: dict[str, LatexTable],
        *,
        project_root: Path | None = None,
    ) -> None:
        self.theorem_specs = theorem_specs
        self.glossary = glossary
        self.glossary_catalog = glossary_catalog
        self.latex_tables = latex_tables
        self.project_root = project_root.resolve() if project_root else None
        self.glossary_entry_count = len(glossary_catalog)
        self.glossary_key_count = len(
            {term.key for term in glossary_catalog}
        )
        self.labels: dict[str, tuple[str, str]] = {}
        self.missing_terms: set[str] = set()
        self.unresolved_references: set[str] = set()
        self.used_terms: set[str] = set()
        self.environment_counts: Counter[str] = Counter()
        self.content_counts: Counter[str] = Counter()
        self.proof_count = 0

        self.has_parts = False
        self.part_level = 1
        self.chapter_level = 1
        self.section_level = 2
        self.subsection_level = 3
        self.subsubsection_level = 4

        self.part = 0
        self.chapter = 0
        self.section = 0
        self.subsection = 0
        self.subsubsection = 0
        self.equation = 0
        self.inequality = 0
        self.algorithm = 0
        self.figure = 0

        self.counter_values: dict[str, int] = {
            spec.counter: 0 for spec in theorem_specs.values()
        }
        self.counter_parents: dict[str, str | None] = {}
        for spec in theorem_specs.values():
            if spec.counter == spec.environment:
                self.counter_parents[spec.counter] = spec.parent
        for spec in theorem_specs.values():
            self.counter_parents.setdefault(
                spec.counter,
                theorem_specs.get(spec.counter, spec).parent,
            )

    def detect_structure(self, blocks: list[dict[str, Any]]) -> None:
        has_numbered_level_one = any(
            block.get("t") == "Header"
            and block["c"][0] == 1
            and "unnumbered" not in block["c"][1][1]
            for block in blocks
        )
        has_level_two = any(
            block.get("t") == "Header" and block["c"][0] == 2 for block in blocks
        )
        self.has_parts = has_numbered_level_one and has_level_two
        if self.has_parts:
            self.part_level = 1
            self.chapter_level = 2
            self.section_level = 3
            self.subsection_level = 4
            self.subsubsection_level = 5

    def reset_counters_for_parent(self, parent: str) -> None:
        for counter, counter_parent in self.counter_parents.items():
            if counter_parent == parent:
                self.counter_values[counter] = 0

    def header_number(self, level: int) -> tuple[str, str, str] | None:
        if self.has_parts and level == self.part_level:
            self.part += 1
            self.section = self.subsection = self.subsubsection = 0
            return f"第 {self.part} 部分", "部分", str(self.part)
        if level == self.chapter_level:
            self.chapter += 1
            self.section = self.subsection = self.subsubsection = 0
            self.equation = 0
            self.algorithm = 0
            self.figure = 0
            self.reset_counters_for_parent("chapter")
            return f"第 {self.chapter} 章", "章", str(self.chapter)
        if level == self.section_level:
            self.section += 1
            self.subsection = self.subsubsection = 0
            self.reset_counters_for_parent("section")
            number = f"{self.chapter}.{self.section}"
            return number, "节", number
        if level == self.subsection_level:
            self.subsection += 1
            self.subsubsection = 0
            number = f"{self.chapter}.{self.section}.{self.subsection}"
            return number, "小节", number
        if level == self.subsubsection_level:
            self.subsubsection += 1
            number = (
                f"{self.chapter}.{self.section}."
                f"{self.subsection}.{self.subsubsection}"
            )
            return number, "小节", number
        return None

    def process_header(self, block: dict[str, Any]) -> dict[str, Any]:
        level, attribute, inlines = block["c"]
        identifier, classes, attributes = attr_parts(attribute)
        if "unnumbered" in classes:
            return block
        number_info = self.header_number(level)
        if number_info is None:
            return block
        visible_number, reference_name, reference_number = number_info
        number_span = span_inline(
            [str_inline(visible_number)], classes=["header-section-number"]
        )
        block["c"][2] = [number_span, space_inline(), *inlines]
        if identifier:
            self.labels[identifier] = (reference_name, reference_number)
        return block

    def counter_number(self, counter: str) -> str:
        value = self.counter_values[counter]
        parent = self.counter_parents.get(counter)
        if parent == "chapter":
            return f"{self.chapter}.{value}"
        if parent == "section":
            return f"{self.chapter}.{self.section}.{value}"
        if parent and parent in self.counter_values:
            return f"{self.counter_number(parent)}.{value}"
        return str(value)

    def process_theorem(self, block: dict[str, Any], environment: str) -> dict[str, Any]:
        spec = self.theorem_specs[environment]
        identifier, classes, attributes = attr_parts(block["c"][0])
        blocks = rewrite_title_markers(block["c"][1])
        blocks, labels = remove_theorem_labels(blocks)

        self.counter_values[spec.counter] += 1
        self.environment_counts[environment] += 1
        self.reset_counters_for_parent(spec.counter)
        number = self.counter_number(spec.counter)
        blocks = replace_first_strong(
            blocks,
            [
                str_inline(spec.printed_name),
                space_inline(),
                str_inline(number),
            ],
            [False],
        )
        blocks = unwrap_emphasis(blocks)

        if labels:
            identifier = labels[0]
        elif identifier.startswith(TITLE_MARKER_PREFIX):
            identifier = ""
        if not identifier:
            identifier = f"{environment}-{number.replace('.', '-')}"
        for label in labels or [identifier]:
            self.labels[label] = (spec.reference_name, number)

        block["c"][0] = make_attr(
            identifier,
            [*classes, "theorem-block", f"env-{environment}"],
            [(key, value) for key, value in attributes],
        )
        block["c"][1] = self.process_blocks(blocks)
        return block

    def algorithm_rows(
        self,
        ordered_list: dict[str, Any],
        depth: int,
        line_counter: list[int],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        items = ordered_list["c"][1]
        unnumbered = {"require", "ensure", "statex", "comment"}
        for item_blocks in items:
            nested_lists = [
                block
                for block in item_blocks
                if block.get("t") == "OrderedList"
            ]
            content_blocks = [
                block
                for block in item_blocks
                if block.get("t") != "OrderedList"
            ]
            kind = remove_algorithm_command_marker(content_blocks)
            content_blocks = [
                block
                for block in content_blocks
                if not (
                    block.get("t") in {"Para", "Plain"}
                    and not block.get("c")
                )
            ]
            content_blocks = self.process_blocks(content_blocks)
            classes = [
                "algorithm-line",
                f"algorithm-{kind}",
                f"algorithm-depth-{min(depth, 6)}",
            ]
            attributes = [("data-depth", str(depth))]
            if kind not in unnumbered:
                line_counter[0] += 1
                attributes.append(("data-line", str(line_counter[0])))
            if content_blocks:
                rows.append(
                    {
                        "t": "Div",
                        "c": [
                            make_attr(
                                classes=classes,
                                attributes=attributes,
                            ),
                            content_blocks,
                        ],
                    }
                )
            for nested in nested_lists:
                rows.extend(
                    self.algorithm_rows(
                        nested,
                        depth + 1,
                        line_counter,
                    )
                )
        return rows

    def process_algorithm(
        self, block: dict[str, Any]
    ) -> dict[str, Any]:
        identifier, classes, attributes = attr_parts(block["c"][0])
        blocks, labels = extract_algorithm_labels(block["c"][1])
        blocks, title = extract_algorithm_caption(blocks)

        self.algorithm += 1
        self.content_counts["algorithm"] += 1
        number = (
            f"{self.chapter}.{self.algorithm}"
            if self.chapter
            else str(self.algorithm)
        )
        if labels:
            identifier = labels[0]
        if not identifier:
            identifier = f"algorithm-{number.replace('.', '-')}"
        for label in labels or [identifier]:
            self.labels[label] = ("算法", number)

        caption = [
            span_inline(
                [str_inline(f"算法 {number}")],
                classes=["algorithm-number"],
            )
        ]
        if title:
            caption.extend(
                [
                    space_inline(),
                    span_inline(title, classes=["algorithm-title"]),
                ]
            )

        line_counter = [0]
        content: list[dict[str, Any]] = [
            {
                "t": "Div",
                "c": [
                    make_attr(classes=["algorithm-caption"]),
                    [{"t": "Para", "c": caption}],
                ],
            }
        ]
        for child in blocks:
            if child.get("t") == "Div":
                _, child_classes, _ = attr_parts(child["c"][0])
                if "algorithmic" in child_classes:
                    algorithmic_content: list[dict[str, Any]] = []
                    for algorithmic_child in child["c"][1]:
                        if algorithmic_child.get("t") == "OrderedList":
                            algorithmic_content.extend(
                                self.algorithm_rows(
                                    algorithmic_child,
                                    0,
                                    line_counter,
                                )
                            )
                        else:
                            algorithmic_content.extend(
                                self.process_blocks([algorithmic_child])
                            )
                    content.append(
                        {
                            "t": "Div",
                            "c": [
                                make_attr(classes=["algorithm-body"]),
                                algorithmic_content,
                            ],
                        }
                    )
                    continue
            content.extend(self.process_blocks([child]))

        block["c"][0] = make_attr(
            identifier,
            [
                *(
                    class_name
                    for class_name in classes
                    if class_name != "algorithm"
                ),
                "algorithm-block",
            ],
            [(key, value) for key, value in attributes],
        )
        block["c"][1] = content
        return block

    def increment_unlabelled_equations(self, source: str) -> None:
        environment_match = re.search(
            r"\\begin\{(equation|align|gather|multline)(\*?)\}", source
        )
        if not environment_match or environment_match.group(2) == "*":
            return
        environment = environment_match.group(1)
        if environment == "equation":
            if r"\notag" not in source and r"\nonumber" not in source:
                self.equation += 1
            return
        body = re.sub(
            r"^.*?\\begin\{(?:align|gather|multline)\}",
            "",
            source,
            count=1,
            flags=re.DOTALL,
        )
        body = re.sub(
            r"\\end\{(?:align|gather|multline)\}.*$",
            "",
            body,
            count=1,
            flags=re.DOTALL,
        )
        rows = re.split(r"(?<!\\)\\\\", body)
        for row in rows:
            if r"\notag" not in row and r"\nonumber" not in row and row.strip():
                self.equation += 1

    def iter_math_nodes(self, value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, list):
            for item in value:
                yield from self.iter_math_nodes(item)
            return
        if not isinstance(value, dict):
            return
        if value.get("t") == "Math":
            yield value
            return
        if "c" in value:
            yield from self.iter_math_nodes(value["c"])

    def process_equations_in_block(
        self, block: dict[str, Any]
    ) -> dict[str, Any]:
        if block.get("t") not in {"Para", "Plain"}:
            return block
        equation_labels: list[tuple[str, str]] = []
        labels_by_math: dict[int, list[str]] = {}
        original_sources: dict[int, str] = {}
        for inline in self.iter_math_nodes(block["c"]):
            if inline["c"][0].get("t") != "DisplayMath":
                continue
            source = inline["c"][1]
            self.content_counts["display-math"] += 1
            original_sources[id(inline)] = source
            labels = re.findall(r"\\label\s*\{([^{}]+)\}", source)
            before = self.equation
            self.increment_unlabelled_equations(source)
            standard_labels = [
                label for label in labels if not label.startswith("ineq:")
            ]
            if standard_labels and self.equation == before:
                self.equation += 1
            self.content_counts["numbered-equation"] += max(
                self.equation - before,
                0,
            )
            if labels:
                for label in labels:
                    if label.startswith("ineq:"):
                        self.inequality += 1
                        number = str(self.inequality)
                        reference_name = "不等式"
                    else:
                        number = f"{self.chapter}.{self.equation}"
                        reference_name = "公式"
                    source = re.sub(
                        rf"\\label\s*\{{{re.escape(label)}\}}",
                        rf"\\tag{{{number}}}",
                        source,
                        count=1,
                    )
                    self.labels[label] = (reference_name, number)
                    equation_labels.append((label, number))
                    labels_by_math.setdefault(id(inline), []).append(label)
                inline["c"][1] = source
        if not equation_labels:
            block["c"] = self.wrap_display_math_sources(
                block["c"], original_sources, {}
            )
            return block
        first_label = equation_labels[0][0]
        additional_anchors = {
            math_id: [
                label for label in labels if label != first_label
            ]
            for math_id, labels in labels_by_math.items()
        }
        block["c"] = self.wrap_display_math_sources(
            block["c"], original_sources, additional_anchors
        )
        return {
            "t": "Div",
            "c": [
                make_attr(first_label, classes=["equation-block"]),
                [block],
            ],
        }

    def wrap_display_math_sources(
        self,
        value: Any,
        original_sources: dict[int, str],
        equation_anchors: dict[int, list[str]],
    ) -> Any:
        if isinstance(value, list):
            result: list[Any] = []
            for item in value:
                if (
                    isinstance(item, dict)
                    and item.get("t") == "Math"
                    and item["c"][0].get("t") == "DisplayMath"
                ):
                    source = original_sources.get(id(item), item["c"][1])
                    encoded = base64.b64encode(
                        source.encode("utf-8")
                    ).decode("ascii")
                    for identifier in equation_anchors.get(id(item), []):
                        result.append(
                            {
                                "t": "Span",
                                "c": [
                                    make_attr(
                                        identifier,
                                        classes=["equation-anchor"],
                                    ),
                                    [],
                                ],
                            }
                        )
                    result.append(
                        {
                            "t": "RawInline",
                            "c": [
                                "html",
                                (
                                    '<span class="display-math-copy-marker" '
                                    f'data-source-tex="{encoded}"></span>'
                                ),
                            ],
                        }
                    )
                    result.append(item)
                else:
                    result.append(
                        self.wrap_display_math_sources(
                            item,
                            original_sources,
                            equation_anchors,
                        )
                    )
            return result
        if not isinstance(value, dict):
            return value
        if "c" in value:
            value["c"] = self.wrap_display_math_sources(
                value["c"], original_sources, equation_anchors
            )
        return value

    def process_child_block_lists(self, value: Any) -> Any:
        if isinstance(value, list):
            if value and all(
                isinstance(item, dict) and item.get("t") in BLOCK_TYPES
                for item in value
            ):
                return self.process_blocks(value)
            return [self.process_child_block_lists(item) for item in value]
        if isinstance(value, dict):
            return {
                key: self.process_child_block_lists(item)
                for key, item in value.items()
            }
        return value

    def process_blocks(
        self, blocks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for block in blocks:
            block_type = block.get("t")
            if block_type == "Header":
                result.append(self.process_header(block))
                continue
            if block_type == "Div":
                _, classes, _ = attr_parts(block["c"][0])
                if "algorithm" in classes:
                    result.append(self.process_algorithm(block))
                    continue
                environment = next(
                    (
                        class_name
                        for class_name in classes
                        if class_name in self.theorem_specs
                    ),
                    None,
                )
                if environment:
                    result.append(self.process_theorem(block, environment))
                    continue
                if "proof" in classes:
                    identifier, _, attributes = attr_parts(block["c"][0])
                    self.proof_count += 1
                    if "proof-block" not in classes:
                        classes.append("proof-block")
                    block["c"][0] = make_attr(
                        identifier,
                        classes,
                        [(key, value) for key, value in attributes],
                    )
                    remove_pandoc_proof_prefix(block["c"][1])
                    block["c"][1] = self.process_blocks(block["c"][1])
                    result.append(block)
                    continue
                block["c"][1] = self.process_blocks(block["c"][1])
                result.append(block)
                continue
            if block_type in {"Para", "Plain"}:
                marker = ast_plain_text(block).strip()
                table_match = re.fullmatch(
                    re.escape(TABLE_MARKER_PREFIX) + r"([0-9]{6})",
                    marker,
                )
                if table_match:
                    table = self.latex_tables.get(table_match.group(1))
                    if table is None:
                        fail(f"找不到暂存表格：{marker}")
                    self.content_counts["latex-table"] += 1
                    result.append(
                        {
                            "t": "RawBlock",
                            "c": ["html", render_latex_table(table)],
                        }
                    )
                    continue
                density_match = re.fullmatch(
                    re.escape(DENSITY_PLOT_MARKER_PREFIX)
                    + r"([a-z0-9-]+)",
                    marker,
                )
                if density_match:
                    name = density_match.group(1)
                    self.content_counts["interactive-density-plot"] += 1
                    result.append(
                        {
                            "t": "RawBlock",
                            "c": [
                                "html",
                                (
                                    '<div class="density-plot" '
                                    f'data-distribution="{name}">'
                                    "<noscript>请启用 JavaScript 以调整参数并绘制密度曲线。"
                                    "</noscript></div>"
                                ),
                            ],
                        }
                    )
                    continue
                result.append(self.process_equations_in_block(block))
                continue
            if block_type == "Figure":
                self.process_figure(block)
                self.content_counts["figure"] += 1
                block["c"] = self.process_child_block_lists(block.get("c"))
                result.append(block)
                continue
            block["c"] = self.process_child_block_lists(block.get("c"))
            result.append(block)
        return result

    def process_figure(self, figure: dict[str, Any]) -> None:
        """Give each figure a visible chapter number and a stable anchor."""

        self.figure += 1
        number = (
            f"{self.chapter}.{self.figure}" if self.chapter else str(self.figure)
        )
        attribute, caption, _body = figure["c"]
        identifier, classes, attributes = attr_parts(attribute)
        if not identifier:
            identifier = f"fig-{self.chapter or 'front'}-{self.figure}"
        if "textbook-figure" not in classes:
            classes.append("textbook-figure")
        figure["c"][0] = make_attr(identifier, classes, attributes)
        self.labels[identifier] = ("图", number)

        caption_blocks = caption[1]
        number_inlines = [
            span_inline(
                [str_inline(f"图 {number}")], classes=["figure-number"]
            ),
            space_inline(),
        ]
        for block in caption_blocks:
            if block.get("t") in {"Para", "Plain"}:
                block["c"] = [*number_inlines, *block["c"]]
                return
        caption_blocks.append({"t": "Plain", "c": number_inlines})

    def term_link(self, key: str) -> dict[str, Any]:
        term = self.glossary.get(key)
        if term is None:
            self.missing_terms.add(key)
            return {
                "t": "Span",
                "c": [
                    make_attr(classes=["term-missing"], attributes=[("data-key", key)]),
                    [str_inline(key)],
                ],
            }
        self.used_terms.add(key)
        chinese = latex_to_html_fragment(term.chinese)
        english = latex_to_html_fragment(term.english)
        visible = (
            chinese
            + '<span class="term-english">（'
            + english
            + "）</span>"
        )
        return {
            "t": "Link",
            "c": [
                make_attr(classes=["term"]),
                [{"t": "RawInline", "c": ["html", visible]}],
                [f"#term-{key}", latex_to_plain(term.english)],
            ],
        }

    @staticmethod
    def reference_suffix_path(text: str) -> tuple[list[str], str]:
        """Parse immediate item selectors such as ``(5)(3.c)``.

        Consecutive parentheses are parallel selectors.  Dots inside one
        selector express the hierarchy used by the source, for example 3.c.
        The returned raw string is sliced from the original text so spacing in
        forms such as ``( 2 )`` is preserved exactly.
        """
        if not text.startswith("("):
            return [], ""
        result: list[str] = []
        cursor = 0
        last_valid_cursor = 0
        while cursor < len(text) and text[cursor] == "(":
            start = cursor + 1
            depth = 1
            cursor += 1
            while cursor < len(text) and depth:
                if text[cursor] == "(":
                    depth += 1
                elif text[cursor] == ")":
                    depth -= 1
                cursor += 1
            if depth:
                break
            value = text[start : cursor - 1].strip()
            if not re.fullmatch(
                r"(?:[0-9]+|[A-Za-z])(?:\.[0-9A-Za-z]+)*",
                value,
            ):
                break
            result.append(value)
            last_valid_cursor = cursor
        return result, text[:last_valid_cursor]

    def annotate_reference_suffixes(
        self, inlines: list[Any]
    ) -> list[Any]:
        for index, inline in enumerate(inlines):
            if not isinstance(inline, dict) or inline.get("t") != "Link":
                continue
            identifier, classes, attributes = attr_parts(inline["c"][0])
            if "textbook-cross-reference" not in classes:
                continue
            if index + 1 >= len(inlines):
                continue
            following = inlines[index + 1]
            if not isinstance(following, dict) or following.get("t") != "Str":
                continue
            suffix_text = str(following.get("c", ""))
            path, raw_suffix = self.reference_suffix_path(suffix_text)
            if not path:
                continue
            hint = "请查看第 " + "、".join(path) + " 项"
            attribute_map = dict(attributes)
            attribute_map["data-reference-items"] = "|".join(path)
            attribute_map["data-reference-hint"] = hint
            inline["c"][0] = make_attr(
                identifier,
                classes,
                list(attribute_map.items()),
            )
            inline["c"][1].append(str_inline(raw_suffix))
            following["c"] = suffix_text[len(raw_suffix) :]
        return [
            inline
            for inline in inlines
            if not (
                isinstance(inline, dict)
                and inline.get("t") == "Str"
                and inline.get("c") == ""
            )
        ]

    def transform_inlines(self, value: Any, *, rewrite_references: bool) -> Any:
        if isinstance(value, list):
            transformed = [
                self.transform_inlines(item, rewrite_references=rewrite_references)
                for item in value
            ]
            return (
                self.annotate_reference_suffixes(transformed)
                if rewrite_references
                else transformed
            )
        if not isinstance(value, dict):
            return value

        node_type = value.get("t")
        if node_type is None:
            return {
                key: self.transform_inlines(
                    item, rewrite_references=rewrite_references
                )
                for key, item in value.items()
            }
        if node_type == "Span":
            attributes = attr_dict(value["c"][0])
            key = attributes.get("acronym-label")
            if key:
                return self.term_link(key)
        if node_type == "Image":
            attribute, _caption, target = value["c"]
            if target[0].startswith("_tikz/"):
                identifier, classes, attributes = attr_parts(attribute)
                if "tikz-image" not in classes:
                    classes.append("tikz-image")
                value["c"][0] = make_attr(
                    identifier,
                    classes,
                    [(key, item) for key, item in attributes],
                )

        if node_type == "Link" and rewrite_references:
            attribute, content, target = value["c"]
            attributes = attr_dict(attribute)
            reference = attributes.get("reference")
            reference_type = attributes.get("reference-type")
            if reference and reference_type:
                label_info = self.labels.get(reference)
                if label_info is None:
                    self.unresolved_references.add(reference)
                    return {
                        "t": "Span",
                        "c": [
                            make_attr(
                                classes=["reference-missing"],
                                attributes=[("data-reference", reference)],
                            ),
                            [str_inline(f"[缺失引用：{reference}]")],
                        ],
                    }
                else:
                    reference_name, number = label_info
                    identifier, classes, attribute_pairs = attr_parts(attribute)
                    if "textbook-cross-reference" not in classes:
                        classes.append("textbook-cross-reference")
                    reference_attributes = dict(attribute_pairs)
                    # The reference is fully resolved by this transformer.
                    # Leaving Pandoc's original markers makes Quarto attempt a
                    # second cross-reference pass over item-suffixed link text.
                    reference_attributes.pop("reference", None)
                    reference_attributes.pop("reference-type", None)
                    reference_attributes["data-reference-key"] = reference
                    reference_attributes["data-reference-kind"] = reference_type
                    reference_attributes["data-reference-title"] = (
                        f"{reference_name} {number}"
                    )
                    attribute = make_attr(
                        identifier,
                        classes,
                        list(reference_attributes.items()),
                    )
                    if reference_type == "eqref":
                        content = [str_inline(f"（{number}）")]
                    elif reference_type == "ref":
                        content = [str_inline(number)]
                    else:
                        content = [str_inline(f"{reference_name} {number}")]
                    value["c"] = [attribute, content, target]

        if "c" in value:
            value["c"] = self.transform_inlines(
                value["c"], rewrite_references=rewrite_references
            )
        return value


    def transform(self, document: dict[str, Any]) -> dict[str, Any]:
        self.detect_structure(document["blocks"])
        document["blocks"] = self.process_blocks(document["blocks"])
        document["blocks"] = rewrite_todo_markers(document["blocks"])
        document = self.transform_inlines(document, rewrite_references=False)
        self.append_glossary(document)
        document = self.transform_inlines(document, rewrite_references=True)
        return document


def parse_latex_to_ast(
    config: BuildConfig,
    runner: CommandRunner,
) -> dict[str, Any]:
    command = [
        config.tools.pandoc,
        "main.tex",
        "--from=latex",
        "--to=json",
        (
            f"--resource-path={config.paths.staged_source_dir}"
            f"{os.pathsep}{config.paths.project_root}"
        ),
    ]
    output = runner.run(command, cwd=config.paths.staged_source_dir)
    return json.loads(output)


def ast_plain_text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(ast_plain_text(item) for item in value)
    if not isinstance(value, dict):
        return ""
    node_type = value.get("t")
    content = value.get("c")
    if node_type == "Str":
        return str(content)
    if node_type in {"Space", "SoftBreak", "LineBreak"}:
        return " "
    if node_type == "Math":
        return latex_to_plain(content[1])
    if node_type == "Note":
        return ""
    if node_type == "MetaString":
        return str(content)
    return ast_plain_text(content)
