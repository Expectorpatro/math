"""Pandoc AST transformation for the staged LaTeX textbook.

This module owns semantic conversion only: it translates Pandoc nodes into the
book's theorem, proof, glossary, algorithm, table, and cross-reference model.
Filesystem staging and final site publication remain separate services.
"""

from __future__ import annotations

import base64
from collections import Counter
import html
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable

from .constants import (
    ALGORITHM_COMMAND_PREFIX,
    ALGORITHM_TITLE_END_PREFIX,
    ALGORITHM_TITLE_START_PREFIX,
    BLOCK_TYPES,
    DENSITY_PLOT_MARKER_PREFIX,
    REMOVE_AST_NODE,
    TABLE_MARKER_PREFIX,
    TITLE_END_PREFIX,
    TITLE_MARKER_PREFIX,
    TITLE_START_PREFIX,
    TODO_COMMANDS,
    TODO_END_PREFIX,
    TODO_START_PREFIX,
)
from .errors import BuildError
from .models import LatexTable, Term, TheoremSpec
from .runtime import CONFIG, RUNNER

PROJECT_ROOT = CONFIG.paths.project_root
STAGED_SOURCE_DIR = CONFIG.paths.staged_source_dir


def fail(message: str) -> None:
    raise BuildError(message)


def run(
    command: list[str],
    *,
    cwd: Path,
    input_text: str | None = None,
) -> str:
    return RUNNER.run(command, cwd=cwd, input_text=input_text)


def scoped_term_key(directory: Path, key: str) -> str:
    relative = directory.relative_to(PROJECT_ROOT).as_posix()
    digest = hashlib.sha1(relative.encode("utf-8")).hexdigest()[:10]
    return f"webscope-{digest}-{key}"


def node_identifier(node: dict[str, Any]) -> str:
    node_type = node.get("t")
    content = node.get("c")
    if node_type in {"Div", "Span", "CodeBlock", "Code", "Link", "Image"}:
        return content[0][0]
    if node_type == "Header":
        return content[1][0]
    if node_type in {"Table", "Figure"}:
        return content[0][0]
    return ""


def attr_parts(attribute: list[Any]) -> tuple[str, list[str], list[list[str]]]:
    return attribute[0], attribute[1], attribute[2]


def attr_dict(attribute: list[Any]) -> dict[str, str]:
    return {key: value for key, value in attribute[2]}


def make_attr(
    identifier: str = "",
    classes: Iterable[str] = (),
    attributes: Iterable[tuple[str, str]] = (),
) -> list[Any]:
    return [identifier, list(classes), [[key, value] for key, value in attributes]]


def str_inline(text: str) -> dict[str, Any]:
    return {"t": "Str", "c": text}


def space_inline() -> dict[str, Any]:
    return {"t": "Space"}


def span_inline(
    content: list[dict[str, Any]], *, classes: Iterable[str] = ()
) -> dict[str, Any]:
    return {"t": "Span", "c": [make_attr(classes=classes), content]}


def trim_inline_spaces(inlines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    while inlines and inlines[0].get("t") in {"Space", "SoftBreak"}:
        inlines.pop(0)
    while inlines and inlines[-1].get("t") in {"Space", "SoftBreak"}:
        inlines.pop()
    return inlines


def remove_labels_from_inlines(
    value: Any, labels: list[str]
) -> Any:
    if isinstance(value, list):
        transformed: list[Any] = []
        for item in value:
            result = remove_labels_from_inlines(item, labels)
            if result is not REMOVE_AST_NODE:
                transformed.append(result)
        return transformed
    if not isinstance(value, dict):
        return value
    if value.get("t") == "Span":
        identifier, _, _ = attr_parts(value["c"][0])
        attributes = attr_dict(value["c"][0])
        label = attributes.get("label") or identifier
        if label:
            if not label.startswith(TITLE_MARKER_PREFIX):
                labels.append(label)
            return REMOVE_AST_NODE
    if "c" in value:
        value["c"] = remove_labels_from_inlines(value["c"], labels)
    return value


def remove_theorem_labels(
    blocks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    labels: list[str] = []
    blocks = remove_labels_from_inlines(blocks, labels)
    return blocks, labels


def rewrite_title_markers(value: Any) -> Any:
    if isinstance(value, list):
        return [rewrite_title_markers(item) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("t") == "Strong":
        inlines = list(value["c"])
        if (
            len(inlines) >= 2
            and inlines[0].get("t") == "Str"
            and inlines[-1].get("t") == "Str"
            and str(inlines[0].get("c", "")).startswith(TITLE_START_PREFIX)
            and str(inlines[-1].get("c", "")).startswith(TITLE_END_PREFIX)
        ):
            title_inlines = trim_inline_spaces(inlines[1:-1])
            value["c"] = [str_inline("（"), *title_inlines, str_inline("）")]
            return value
    if "c" in value:
        value["c"] = rewrite_title_markers(value["c"])
    return value


def rewrite_todo_markers(value: Any) -> Any:
    if isinstance(value, list):
        return [rewrite_todo_markers(item) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("t") == "Strong":
        inlines = list(value["c"])
        if (
            len(inlines) >= 2
            and inlines[0].get("t") == "Str"
            and inlines[-1].get("t") == "Str"
        ):
            start = str(inlines[0].get("c", ""))
            end = str(inlines[-1].get("c", ""))
            if start.startswith(TODO_START_PREFIX):
                kind = start[len(TODO_START_PREFIX) :]
                if kind in TODO_COMMANDS and end == f"{TODO_END_PREFIX}{kind}":
                    return {
                        "t": "Span",
                        "c": [
                            make_attr(
                                classes=["todo-note", f"todo-{kind}"],
                                attributes=[("role", "note")],
                            ),
                            trim_inline_spaces(inlines[1:-1]),
                        ],
                    }
    if "c" in value:
        value["c"] = rewrite_todo_markers(value["c"])
    return value


def replace_first_strong(
    value: Any, content: list[dict[str, Any]], replaced: list[bool]
) -> Any:
    if replaced[0]:
        return value
    if isinstance(value, list):
        return [replace_first_strong(item, content, replaced) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("t") == "Strong":
        value["c"] = content
        replaced[0] = True
        return value
    if "c" in value:
        value["c"] = replace_first_strong(value["c"], content, replaced)
    return value


def unwrap_emphasis(value: Any) -> Any:
    if isinstance(value, list):
        result: list[Any] = []
        for item in value:
            transformed = unwrap_emphasis(item)
            if isinstance(transformed, dict) and transformed.get("t") == "Emph":
                result.extend(transformed["c"])
            else:
                result.append(transformed)
        return result
    if not isinstance(value, dict):
        return value
    if "c" in value:
        value["c"] = unwrap_emphasis(value["c"])
    return value


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


def latex_to_plain(text: str) -> str:
    replacements = {
        r"\sigma": "σ",
        r"\lambda": "λ",
        r"\pi": "π",
        r"\mu": "μ",
        r"\alpha": "α",
        r"\beta": "β",
        r"\gamma": "γ",
        r"\infty": "∞",
    }
    result = text
    for source, replacement in replacements.items():
        result = result.replace(source, replacement)
    result = re.sub(r"\\(?:textbf|textit|emph|mathrm|operatorname)\s*\{([^{}]*)\}", r"\1", result)
    result = result.replace("$", "").replace("~", " ")
    result = result.replace(r"\,", " ").replace(r"\ ", " ")
    result = re.sub(r"\\([A-Za-z]+)", r"\1", result)
    result = result.replace("{", "").replace("}", "")
    return " ".join(result.split())


def latex_to_html_fragment(text: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for match in re.finditer(r"\$(.+?)\$", text, flags=re.DOTALL):
        pieces.append(html.escape(latex_to_plain(text[cursor : match.start()])))
        math_source = match.group(1).strip()
        pieces.append(
            '<span class="math inline">\\('
            + html.escape(math_source)
            + "\\)</span>"
        )
        cursor = match.end()
    pieces.append(html.escape(latex_to_plain(text[cursor:])))
    return "".join(pieces)


def latex_to_table_html_fragment(text: str) -> str:
    """Render table cells without Quarto consuming TeX backslashes."""
    pieces: list[str] = []
    cursor = 0
    for match in re.finditer(r"\$(.+?)\$", text, flags=re.DOTALL):
        pieces.append(html.escape(latex_to_plain(text[cursor : match.start()])))
        math_source = html.escape(match.group(1).strip()).replace(
            "\\", "&#92;"
        )
        pieces.append(
            '<span class="math inline">&#92;('
            + math_source
            + "&#92;)</span>"
        )
        cursor = match.end()
    pieces.append(html.escape(latex_to_plain(text[cursor:])))
    return "".join(pieces)


def render_latex_table(table: LatexTable) -> str:
    parts = [
        '<div class="textbook-table-scroll textbook-latex-table-scroll" '
        'role="region" tabindex="0">',
        '<table class="textbook-latex-table">',
    ]
    if table.caption:
        parts.append(
            "<caption>" + html.escape(latex_to_plain(table.caption)) + "</caption>"
        )
    for row_index, row in enumerate(table.rows):
        if row_index == 0:
            parts.append("<thead>")
        elif row_index == 1:
            parts.append("</thead><tbody>")
        row_classes: list[str] = []
        if row.rule_above:
            row_classes.append("latex-table-rule-above")
        if row.rule_below:
            row_classes.append("latex-table-rule-below")
        class_attribute = (
            f' class="{" ".join(row_classes)}"' if row_classes else ""
        )
        parts.append(f"<tr{class_attribute}>")
        column = 0
        for cell in row.cells:
            start_column = column
            column += cell.colspan
            alignment = (
                cell.alignment
                or table.alignments[
                    min(start_column, len(table.alignments) - 1)
                ]
            )
            classes = [f"latex-table-align-{alignment}"]
            if column in table.vertical_rules:
                classes.append("latex-table-vrule-right")
            tag = "th" if row_index == 0 else "td"
            attributes = [f'class="{" ".join(classes)}"']
            if cell.colspan > 1:
                attributes.append(f'colspan="{cell.colspan}"')
            if cell.diagonal is not None:
                lower_left, upper_right = cell.diagonal
                cell_markup = (
                    '<span class="latex-table-diagbox">'
                    '<span class="latex-table-diagbox-upper">'
                    + latex_to_table_html_fragment(upper_right)
                    + "</span>"
                    '<span class="latex-table-diagbox-lower">'
                    + latex_to_table_html_fragment(lower_left)
                    + "</span></span>"
                )
            else:
                cell_markup = latex_to_table_html_fragment(cell.content)
            parts.append(
                f"<{tag} {' '.join(attributes)}>{cell_markup}</{tag}>"
            )
        parts.append("</tr>")
    if len(table.rows) == 1:
        parts.append("</thead>")
    else:
        parts.append("</tbody>")
    parts.extend(("</table>", "</div>"))
    return "".join(parts)


class BookTransformer:
    def __init__(
        self,
        theorem_specs: dict[str, TheoremSpec],
        glossary: dict[str, Term],
        glossary_catalog: list[Term],
        latex_tables: dict[str, LatexTable],
    ) -> None:
        self.theorem_specs = theorem_specs
        self.glossary = glossary
        self.glossary_catalog = glossary_catalog
        self.latex_tables = latex_tables
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

    def append_glossary(self, document: dict[str, Any]) -> None:
        greek_letters = {
            "α": "A",
            "β": "B",
            "γ": "G",
            "λ": "L",
            "μ": "M",
            "π": "P",
            "σ": "S",
        }

        def english_name(term: Term) -> str:
            return latex_to_plain(term.english).strip()

        def term_letter(term: Term) -> str:
            name = english_name(term)
            if name and name[0] in greek_letters:
                return greek_letters[name[0]]
            match = re.search(r"[A-Za-z]", name)
            return match.group(0).upper() if match else "#"

        def term_sort_key(term: Term) -> tuple[str, str, str, str]:
            return (
                english_name(term).casefold(),
                latex_to_plain(term.chinese).casefold(),
                term.key.casefold(),
                term.source.casefold(),
            )

        groups: dict[str, list[Term]] = {
            letter: [] for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        }
        groups["#"] = []
        for term in sorted(
            self.glossary_catalog,
            key=term_sort_key,
        ):
            groups[term_letter(term)].append(term)

        letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        if groups["#"]:
            letters.append("#")

        blocks: list[dict[str, Any]] = []
        if self.has_parts:
            blocks.append(
                {
                    "t": "Header",
                    "c": [
                        self.part_level,
                        make_attr(
                            "glossary-part",
                            classes=["glossary-part"],
                        ),
                        [str_inline("中英术语表")],
                    ],
                }
            )

        blocks.append(
            {
                "t": "Header",
                "c": [
                    self.chapter_level,
                    make_attr(
                        "glossary",
                        classes=["glossary-page"],
                    ),
                    [str_inline("中英术语表")],
                ],
            }
        )
        blocks.append(
            {
                "t": "Div",
                "c": [
                    make_attr(classes=["glossary-summary"]),
                    [
                        {
                            "t": "Para",
                            "c": [
                                str_inline("共收录"),
                                space_inline(),
                                {
                                    "t": "Strong",
                                    "c": [
                                        str_inline(
                                            str(self.glossary_entry_count)
                                        )
                                    ],
                                },
                                space_inline(),
                                str_inline("条"),
                                space_inline(),
                                {
                                    "t": "Code",
                                    "c": [
                                        make_attr(),
                                        "NewTerm",
                                    ],
                                },
                                str_inline("，对应"),
                                space_inline(),
                                {
                                    "t": "Strong",
                                    "c": [
                                        str_inline(
                                            str(self.glossary_key_count)
                                        )
                                    ],
                                },
                                space_inline(),
                                str_inline(
                                    "个索引键。术语按英文名称的首字母排列，"
                                    "每个字母独立成页并纳入全站搜索。"
                                ),
                            ],
                        }
                    ],
                ],
            }
        )

        alphabet_links: list[dict[str, Any]] = []
        for letter in letters:
            target_id = (
                "glossary-letter-other"
                if letter == "#"
                else f"glossary-letter-{letter}"
            )
            label = "其他" if letter == "#" else letter
            alphabet_links.extend(
                [
                    {
                        "t": "Link",
                        "c": [
                            make_attr(
                                classes=["glossary-letter-link"]
                            ),
                            [
                                {
                                    "t": "Span",
                                    "c": [
                                        make_attr(
                                            classes=[
                                                "glossary-letter-name"
                                            ]
                                        ),
                                        [str_inline(label)],
                                    ],
                                },
                                space_inline(),
                                {
                                    "t": "Span",
                                    "c": [
                                        make_attr(
                                            classes=[
                                                "glossary-letter-count"
                                            ]
                                        ),
                                        [
                                            str_inline(
                                                str(len(groups[letter]))
                                            )
                                        ],
                                    ],
                                },
                            ],
                            [f"#{target_id}", ""],
                        ],
                    },
                    space_inline(),
                ]
            )
        blocks.append(
            {
                "t": "Div",
                "c": [
                    make_attr(classes=["glossary-alphabet"]),
                    [{"t": "Para", "c": alphabet_links}],
                ],
            }
        )

        key_counts = Counter(
            term.key for term in self.glossary_catalog
        )
        first_key_occurrence: set[str] = set()

        def letter_target(letter: str) -> str:
            return (
                "glossary-letter-other"
                if letter == "#"
                else f"glossary-letter-{letter}"
            )

        def navigation(letter_index: int) -> dict[str, Any]:
            inlines: list[dict[str, Any]] = []
            if letter_index > 0:
                previous = letters[letter_index - 1]
                inlines.extend(
                    [
                        {
                            "t": "Link",
                            "c": [
                                make_attr(
                                    classes=["glossary-nav-link"]
                                ),
                                [
                                    str_inline(
                                        "← "
                                        + (
                                            "其他"
                                            if previous == "#"
                                            else previous
                                        )
                                    )
                                ],
                                [f"#{letter_target(previous)}", ""],
                            ],
                        },
                        space_inline(),
                    ]
                )
            inlines.extend(
                [
                    {
                        "t": "Link",
                        "c": [
                            make_attr(
                                classes=["glossary-nav-link"]
                            ),
                            [str_inline("A–Z 总览")],
                            ["#glossary", ""],
                        ],
                    },
                    space_inline(),
                ]
            )
            if letter_index + 1 < len(letters):
                following = letters[letter_index + 1]
                inlines.append(
                    {
                        "t": "Link",
                        "c": [
                            make_attr(
                                classes=["glossary-nav-link"]
                            ),
                            [
                                str_inline(
                                    (
                                        "其他"
                                        if following == "#"
                                        else following
                                    )
                                    + " →"
                                )
                            ],
                            [f"#{letter_target(following)}", ""],
                        ],
                    }
                )
            return {
                "t": "Div",
                "c": [
                    make_attr(classes=["glossary-navigation"]),
                    [{"t": "Para", "c": inlines}],
                ],
            }

        for letter_index, letter in enumerate(letters):
            label = "其他" if letter == "#" else letter
            terms = groups[letter]
            blocks.append(
                {
                    "t": "Header",
                    "c": [
                        self.chapter_level,
                        make_attr(
                            letter_target(letter),
                            classes=["glossary-page"],
                        ),
                        [str_inline(f"{label} · 中英术语")],
                    ],
                }
            )
            blocks.append(navigation(letter_index))
            blocks.append(
                {
                    "t": "Para",
                    "c": [
                        str_inline(f"本页共 {len(terms)} 个术语，"),
                        str_inline("按英文名称排序。"),
                    ],
                }
            )

            if not terms:
                blocks.append(
                    {
                        "t": "Div",
                        "c": [
                            make_attr(
                                classes=["glossary-empty"]
                            ),
                            [
                                {
                                    "t": "Para",
                                    "c": [
                                        str_inline(
                                            "当前没有以该字母开头的术语。"
                                        )
                                    ],
                                }
                            ],
                        ],
                    }
                )
                continue

            for term in terms:
                aliases: list[str] = []
                if key_counts[term.key] == 1:
                    entry_identifier = f"term-{term.key}"
                else:
                    source_directory = (
                        PROJECT_ROOT / term.source
                    ).parent
                    scoped_key = scoped_term_key(
                        source_directory,
                        term.key,
                    )
                    if term.key not in first_key_occurrence:
                        entry_identifier = f"term-{term.key}"
                        aliases.append(f"term-{scoped_key}")
                        first_key_occurrence.add(term.key)
                    else:
                        entry_identifier = f"term-{scoped_key}"

                alias_inlines = [
                    {
                        "t": "Span",
                        "c": [
                            make_attr(
                                alias,
                                classes=["glossary-alias"],
                            ),
                            [],
                        ],
                    }
                    for alias in aliases
                ]
                english = {
                    "t": "RawInline",
                    "c": [
                        "html",
                        latex_to_html_fragment(term.english),
                    ],
                }
                chinese = {
                    "t": "RawInline",
                    "c": [
                        "html",
                        latex_to_html_fragment(term.chinese),
                    ],
                }
                blocks.append(
                    {
                        "t": "Div",
                        "c": [
                            make_attr(
                                classes=["glossary-entry"],
                                attributes=[
                                    ("data-term-key", term.key),
                                    ("data-term-source", term.source),
                                ],
                            ),
                            [
                                {
                                    "t": "Div",
                                    "c": [
                                        make_attr(
                                            classes=[
                                                "glossary-entry-main"
                                            ]
                                        ),
                                        [
                                            {
                                                "t": "Header",
                                                "c": [
                                                    self.chapter_level + 1,
                                                    make_attr(
                                                        entry_identifier,
                                                        classes=[
                                                            "glossary-term-heading",
                                                            "unlisted",
                                                        ],
                                                    ),
                                                    [
                                                        *alias_inlines,
                                                        english,
                                                        space_inline(),
                                                        {
                                                            "t": "Span",
                                                            "c": [
                                                                make_attr(
                                                                    classes=[
                                                                        "glossary-chinese"
                                                                    ]
                                                                ),
                                                                [chinese],
                                                            ],
                                                        },
                                                    ],
                                                ],
                                            }
                                        ],
                                    ],
                                },
                                {
                                    "t": "Div",
                                    "c": [
                                        make_attr(
                                            classes=[
                                                "glossary-entry-meta"
                                            ]
                                        ),
                                        [
                                            {
                                                "t": "Para",
                                                "c": [
                                                    str_inline("索引"),
                                                    space_inline(),
                                                    {
                                                        "t": "Code",
                                                        "c": [
                                                            make_attr(),
                                                            term.key,
                                                        ],
                                                    },
                                                    space_inline(),
                                                    str_inline("·"),
                                                    space_inline(),
                                                    str_inline(term.source),
                                                ],
                                            }
                                        ],
                                    ],
                                },
                            ],
                        ],
                    }
                )
            blocks.append(navigation(letter_index))

        document["blocks"].extend(blocks)

    def transform(self, document: dict[str, Any]) -> dict[str, Any]:
        self.detect_structure(document["blocks"])
        document["blocks"] = self.process_blocks(document["blocks"])
        document["blocks"] = rewrite_todo_markers(document["blocks"])
        document = self.transform_inlines(document, rewrite_references=False)
        self.append_glossary(document)
        document = self.transform_inlines(document, rewrite_references=True)
        return document


def parse_latex_to_ast() -> dict[str, Any]:
    command = [
        CONFIG.tools.pandoc,
        "main.tex",
        "--from=latex",
        "--to=json",
        f"--resource-path={STAGED_SOURCE_DIR}{os.pathsep}{PROJECT_ROOT}",
    ]
    output = run(command, cwd=STAGED_SOURCE_DIR)
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
