#!/usr/bin/env python3
"""Build the LaTeX textbook as a multi-page HTML site.

The LaTeX sources remain the single source of truth.  This script stages copies
of the .tex files, lets Pandoc parse them into its JSON AST, applies the
project-specific theorem/glossary/reference rules, and asks Pandoc to write
chunked HTML.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from collections import Counter
import hashlib
import html
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import date as calendar_date
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlencode, urlsplit


HTML_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = HTML_DIR.parent
BUILD_DIR = HTML_DIR / ".build"
STAGED_SOURCE_DIR = BUILD_DIR / "source"
TIKZ_CACHE_DIR = BUILD_DIR / "tikz-cache"
TIKZ_WORK_DIR = BUILD_DIR / "tikz-work"
DEFAULT_OUTPUT_DIR = HTML_DIR / "site"
HOME_CONTENT = HTML_DIR / "home.md"
BIBLIOGRAPHY_STYLE = HTML_DIR / "textbook.csl"
DENSITY_PLOT_SCRIPT = HTML_DIR / "density-plots.js"
DENSITY_PLOT_INCLUDE = HTML_DIR / "density-plots.html"
DENSITY_LOADER_SCRIPT = HTML_DIR / "density-loader.js"
DENSITY_MATH_SCRIPT = HTML_DIR / "density-math.js"
DENSITY_PROBE_SCRIPT = HTML_DIR / "density-probe.js"
FORMULA_COPY_SCRIPT = HTML_DIR / "formula-copy.js"
FORMULA_COPY_INCLUDE = HTML_DIR / "formula-copy.html"
TEXTBOOK_UI_SCRIPT = HTML_DIR / "textbook-ui.js"
FAVICON = HTML_DIR / "favicon.svg"
SITE_META = HTML_DIR / "site-meta.json"
CHAPTER_PROGRESS = HTML_DIR / "chapter-progress.json"
NOTATION_CATALOG = HTML_DIR / "notation-catalog.json"
MAIN_TEX = PROJECT_ROOT / "main.tex"
SETTINGS_TEX = PROJECT_ROOT / "settings.tex"
QUARTO = Path(
    os.environ.get(
        "QUARTO",
        "/Applications/Positron.app/Contents/Resources/app/quarto/bin/quarto",
    )
)
QUARTO_PROJECT_DIR = BUILD_DIR / "quarto"

TITLE_MARKER_PREFIX = "web-title:"
TITLE_START_PREFIX = "WEBTITLESTART"
TITLE_END_PREFIX = "WEBTITLEEND"
ALGORITHM_TITLE_START_PREFIX = "WEBALGOTITLESTART"
ALGORITHM_TITLE_END_PREFIX = "WEBALGOTITLEEND"
ALGORITHM_COMMAND_PREFIX = "WEBALGOCMD-"
DENSITY_PLOT_MARKER_PREFIX = "WEBDENSITYPLOT-"
TODO_START_PREFIX = "WEBTODOSTART-"
TODO_END_PREFIX = "WEBTODOEND-"
TODO_COMMANDS = {"info", "unsure", "change", "improvement"}
TABLE_MARKER_PREFIX = "WEBLATEXTABLE-"
DENSITY_PLOT_NAMES = {
    "uniform",
    "normal",
    "chi-square",
    "student-t",
    "f",
    "gamma",
    "beta",
}

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

SITE_DESCRIPTION = (
    "持续整理的在线数学教材，涵盖代数、分析、概率、优化与统计，"
    "强调逻辑自洽、证明完整与持续维护。"
)

BLOCK_TYPES = {
    "BlockQuote",
    "BulletList",
    "CodeBlock",
    "DefinitionList",
    "Div",
    "Figure",
    "Header",
    "HorizontalRule",
    "LineBlock",
    "OrderedList",
    "Para",
    "Plain",
    "RawBlock",
    "Table",
}
REMOVE_AST_NODE = object()


@dataclass(frozen=True)
class TheoremSpec:
    environment: str
    printed_name: str
    counter: str
    parent: str | None
    reference_name: str


@dataclass(frozen=True)
class Term:
    key: str
    english: str
    chinese: str
    source: str


@dataclass
class QuartoPage:
    source_path: Path
    blocks: list[dict[str, Any]]
    part: str | None
    sidebar_visible: bool = True


@dataclass(frozen=True)
class ComputationGroup:
    title: str
    result_paths: tuple[Path, ...]


@dataclass(frozen=True)
class LatexTableCell:
    content: str
    colspan: int = 1
    alignment: str | None = None
    diagonal: tuple[str, str] | None = None


@dataclass(frozen=True)
class LatexTableRow:
    cells: tuple[LatexTableCell, ...]
    rule_above: bool = False
    rule_below: bool = False


@dataclass(frozen=True)
class LatexTable:
    caption: str
    alignments: tuple[str, ...]
    vertical_rules: frozenset[int]
    rows: tuple[LatexTableRow, ...]


STAGED_LATEX_TABLES: dict[str, LatexTable] = {}


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.identifiers: set[str] = set()
        self.duplicate_identifiers: set[str] = set()
        self.links: list[str] = []

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        values = {key: value for key, value in attributes}
        identifier = values.get("id")
        if identifier:
            if identifier in self.identifiers:
                self.duplicate_identifiers.add(identifier)
            self.identifiers.add(identifier)
        href = values.get("href")
        if tag == "a" and href:
            self.links.append(href)


def log(message: str) -> None:
    print(f"[web] {message}")


def fail(message: str) -> None:
    raise RuntimeError(message)


def run(
    command: list[str],
    *,
    cwd: Path,
    input_text: str | None = None,
    environment: dict[str, str] | None = None,
) -> str:
    process_environment = os.environ.copy()
    if environment:
        process_environment.update(environment)
    result = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        env=process_environment,
    )
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        fail(f"命令执行失败（退出码 {result.returncode}）：{' '.join(command)}")
    return result.stdout


def ensure_tool(name: str) -> None:
    if shutil.which(name) is None:
        fail(f"找不到 {name}。请先安装 Pandoc 3.x。")


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def clean_generated_directory(path: Path) -> None:
    if not is_inside(path, HTML_DIR):
        fail(f"拒绝清理 html/ 之外的目录：{path}")
    if path.exists():
        shutil.rmtree(path)


def strip_tex_comments(text: str) -> str:
    """Strip ordinary TeX comments while preserving escaped percent signs."""
    cleaned: list[str] = []
    for line in text.splitlines():
        cut = len(line)
        for index, char in enumerate(line):
            if char != "%":
                continue
            slash_count = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                slash_count += 1
                cursor -= 1
            if slash_count % 2 == 0:
                cut = index
                break
        cleaned.append(line[:cut])
    return "\n".join(cleaned)


def skip_space(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def read_balanced(
    text: str, position: int, opening: str, closing: str
) -> tuple[str, int]:
    if position >= len(text) or text[position] != opening:
        raise ValueError(f"expected {opening!r} at character {position}")
    depth = 1
    cursor = position + 1
    start = cursor
    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start:cursor], cursor + 1
        cursor += 1
    raise ValueError(f"unclosed {opening!r} at character {position}")


def patch_todo_macros(text: str, marker_counter: list[int]) -> str:
    """Preserve project todo macros as styled inline notes in the web AST."""
    pattern = re.compile(
        r"\\(?P<kind>info|unsure|change|improvement)\b"
    )
    pieces: list[str] = []
    cursor = 0
    while True:
        match = pattern.search(text, cursor)
        if match is None:
            pieces.append(text[cursor:])
            break
        pieces.append(text[cursor : match.start()])
        position = skip_space(text, match.end())
        try:
            if position < len(text) and text[position] == "[":
                _, position = read_balanced(text, position, "[", "]")
                position = skip_space(text, position)
            content, end = read_balanced(text, position, "{", "}")
        except ValueError:
            pieces.append(match.group(0))
            cursor = match.end()
            continue
        kind = match.group("kind")
        pieces.append(
            rf"\textbf{{{TODO_START_PREFIX}{kind} "
            + content
            + rf" {TODO_END_PREFIX}{kind}}}"
        )
        marker_counter[0] += 1
        cursor = end
    return "".join(pieces)


def expand_table_column_repetitions(specification: str) -> str:
    """Expand TeX ``*{n}{...}`` column specifications recursively."""
    output: list[str] = []
    cursor = 0
    while cursor < len(specification):
        if specification[cursor] != "*":
            output.append(specification[cursor])
            cursor += 1
            continue
        position = skip_space(specification, cursor + 1)
        try:
            count_text, position = read_balanced(
                specification, position, "{", "}"
            )
            position = skip_space(specification, position)
            repeated, position = read_balanced(
                specification, position, "{", "}"
            )
            count = int(count_text.strip())
        except (ValueError, TypeError):
            output.append("*")
            cursor += 1
            continue
        output.append(expand_table_column_repetitions(repeated) * count)
        cursor = position
    return "".join(output)


def parse_table_column_specification(
    specification: str,
) -> tuple[list[str], set[int]]:
    """Return column alignments and 1-based boundaries carrying ``|``."""
    specification = expand_table_column_repetitions(specification)
    alignments: list[str] = []
    vertical_rules: set[int] = set()
    cursor = 0
    while cursor < len(specification):
        char = specification[cursor]
        if char.isspace():
            cursor += 1
            continue
        if char == "|":
            vertical_rules.add(len(alignments))
            cursor += 1
            continue
        if char in "><@!":
            position = skip_space(specification, cursor + 1)
            try:
                _, cursor = read_balanced(
                    specification, position, "{", "}"
                )
            except ValueError:
                cursor += 1
            continue
        if char in "lcrX":
            alignments.append(
                {
                    "l": "left",
                    "c": "center",
                    "r": "right",
                    "X": "center",
                }[char]
            )
            cursor += 1
            continue
        if char in "pmb":
            alignments.append("left")
            position = skip_space(specification, cursor + 1)
            try:
                _, cursor = read_balanced(
                    specification, position, "{", "}"
                )
            except ValueError:
                cursor += 1
            continue
        cursor += 1
    return alignments, vertical_rules


def split_latex_table_rows(content: str) -> list[str]:
    rows: list[str] = []
    current: list[str] = []
    depth = 0
    cursor = 0
    while cursor < len(content):
        char = content[cursor]
        if char == "\\" and cursor + 1 < len(content):
            following = content[cursor + 1]
            if following == "\\" and depth == 0:
                rows.append("".join(current))
                current = []
                cursor += 2
                continue
            current.extend((char, following))
            cursor += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}" and depth:
            depth -= 1
        current.append(char)
        cursor += 1
    rows.append("".join(current))
    return rows


def split_latex_table_cells(row: str) -> list[str]:
    cells: list[str] = []
    current: list[str] = []
    depth = 0
    cursor = 0
    while cursor < len(row):
        char = row[cursor]
        if char == "\\" and cursor + 1 < len(row):
            current.extend((char, row[cursor + 1]))
            cursor += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}" and depth:
            depth -= 1
        if char == "&" and depth == 0:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        cursor += 1
    cells.append("".join(current).strip())
    return cells


def parse_latex_table_cell(content: str) -> LatexTableCell:
    stripped = content.strip()
    if stripped.startswith(r"\multicolumn"):
        position = skip_space(stripped, len(r"\multicolumn"))
        try:
            colspan_text, position = read_balanced(
                stripped, position, "{", "}"
            )
            position = skip_space(stripped, position)
            cell_spec, position = read_balanced(
                stripped, position, "{", "}"
            )
            position = skip_space(stripped, position)
            cell_content, position = read_balanced(
                stripped, position, "{", "}"
            )
            alignments, _ = parse_table_column_specification(cell_spec)
            return LatexTableCell(
                content=cell_content.strip() + stripped[position:].strip(),
                colspan=max(int(colspan_text.strip()), 1),
                alignment=alignments[0] if alignments else "center",
            )
        except (ValueError, TypeError):
            pass
    if stripped.startswith(r"\diagbox"):
        position = skip_space(stripped, len(r"\diagbox"))
        try:
            lower_left, position = read_balanced(
                stripped, position, "{", "}"
            )
            position = skip_space(stripped, position)
            upper_right, position = read_balanced(
                stripped, position, "{", "}"
            )
            return LatexTableCell(
                content="",
                diagonal=(lower_left.strip(), upper_right.strip()),
                alignment="center",
            )
        except ValueError:
            pass
    return LatexTableCell(content=stripped)


TABLE_RULE_PATTERN = re.compile(
    r"\\(?:toprule|midrule|bottomrule|hline)\b"
    r"|\\cline\s*\{[^{}]*\}"
)


def parse_latex_table(
    table_source: str,
) -> LatexTable | None:
    tabular_match = re.search(
        r"\\begin\s*\{(?P<environment>tabularx|tabular)\}",
        table_source,
    )
    if tabular_match is None:
        return None
    environment = tabular_match.group("environment")
    position = skip_space(table_source, tabular_match.end())
    try:
        if environment == "tabularx":
            _, position = read_balanced(table_source, position, "{", "}")
            position = skip_space(table_source, position)
        specification, position = read_balanced(
            table_source, position, "{", "}"
        )
    except ValueError:
        return None
    end_marker = rf"\end{{{environment}}}"
    tabular_end = table_source.find(end_marker, position)
    if tabular_end < 0:
        return None

    caption = ""
    caption_match = re.search(r"\\caption\b", table_source)
    if caption_match is not None:
        caption_position = skip_space(table_source, caption_match.end())
        try:
            if (
                caption_position < len(table_source)
                and table_source[caption_position] == "["
            ):
                _, caption_position = read_balanced(
                    table_source, caption_position, "[", "]"
                )
                caption_position = skip_space(
                    table_source, caption_position
                )
            caption, _ = read_balanced(
                table_source, caption_position, "{", "}"
            )
        except ValueError:
            caption = ""

    parsed_rows: list[LatexTableRow] = []
    for raw_row in split_latex_table_rows(
        strip_tex_comments(table_source[position:tabular_end])
    ):
        has_rule = TABLE_RULE_PATTERN.search(raw_row) is not None
        cleaned = TABLE_RULE_PATTERN.sub("", raw_row).strip()
        if not cleaned:
            if has_rule and parsed_rows:
                previous = parsed_rows[-1]
                parsed_rows[-1] = LatexTableRow(
                    cells=previous.cells,
                    rule_above=previous.rule_above,
                    rule_below=True,
                )
            continue
        cells = tuple(
            parse_latex_table_cell(cell)
            for cell in split_latex_table_cells(cleaned)
        )
        parsed_rows.append(
            LatexTableRow(cells=cells, rule_above=has_rule)
        )
    if not parsed_rows:
        return None

    actual_column_count = max(
        sum(cell.colspan for cell in row.cells)
        for row in parsed_rows
    )
    alignments, vertical_rules = parse_table_column_specification(
        specification
    )
    alignments = (alignments + ["center"] * actual_column_count)[
        :actual_column_count
    ]
    vertical_rules = {
        boundary
        for boundary in vertical_rules
        if 0 < boundary <= actual_column_count
    }
    return LatexTable(
        caption=caption.strip(),
        alignments=tuple(alignments),
        vertical_rules=frozenset(vertical_rules),
        rows=tuple(parsed_rows),
    )


def patch_latex_tables(
    text: str, marker_counter: list[int]
) -> str:
    pattern = re.compile(
        r"^[ \t]*\\begin\s*\{table\}(?:\s*\[[^\]]*\])?"
        r"(?P<body>.*?)"
        r"^[ \t]*\\end\s*\{table\}",
        flags=re.DOTALL | re.MULTILINE,
    )

    def replacement(match: re.Match[str]) -> str:
        table = parse_latex_table(match.group(0))
        if table is None:
            return match.group(0)
        marker_counter[0] += 1
        marker = f"{marker_counter[0]:06d}"
        STAGED_LATEX_TABLES[marker] = table
        return rf"\par\textbf{{{TABLE_MARKER_PREFIX}{marker}}}\par"

    return pattern.sub(replacement, text)


def parse_new_terms(text: str, source: Path) -> list[Term]:
    terms: list[Term] = []
    cursor = 0
    command = r"\NewTerm"
    while True:
        start = text.find(command, cursor)
        if start < 0:
            break
        position = skip_space(text, start + len(command))
        try:
            if position < len(text) and text[position] == "[":
                _, position = read_balanced(text, position, "[", "]")
                position = skip_space(text, position)
            values: list[str] = []
            for _ in range(3):
                value, position = read_balanced(text, position, "{", "}")
                values.append(value.strip())
                position = skip_space(text, position)
        except ValueError:
            cursor = start + len(command)
            continue
        key, english_name, chinese_name = values
        if key:
            terms.append(
                Term(
                    key=key,
                    english=english_name,
                    chinese=chinese_name,
                    source=str(source.relative_to(PROJECT_ROOT)),
                )
            )
        cursor = position
    return terms


def load_glossary() -> tuple[
    dict[str, Term],
    dict[Path, dict[str, Term]],
    set[str],
    list[str],
    list[Term],
]:
    glossary: dict[str, Term] = {}
    terms_by_directory: dict[Path, dict[str, Term]] = {}
    conflicting_keys: set[str] = set()
    warnings: list[str] = []
    catalog: list[Term] = []
    for path in sorted(PROJECT_ROOT.rglob("english.tex")):
        if is_inside(path, HTML_DIR):
            continue
        text = strip_tex_comments(path.read_text(encoding="utf-8"))
        for term in parse_new_terms(text, path):
            catalog.append(term)
            terms_by_directory.setdefault(path.parent, {})[term.key] = term
            previous = glossary.get(term.key)
            if previous and (
                previous.english != term.english or previous.chinese != term.chinese
            ):
                conflicting_keys.add(term.key)
                warnings.append(
                    f"术语 {term.key!r} 在 {previous.source} 与 {term.source} 中定义不同"
                )
                continue
            glossary[term.key] = term
    return (
        glossary,
        terms_by_directory,
        conflicting_keys,
        warnings,
        catalog,
    )


def parse_theorem_specs() -> dict[str, TheoremSpec]:
    text = strip_tex_comments(SETTINGS_TEX.read_text(encoding="utf-8"))
    cref_names: dict[str, str] = {}
    for match in re.finditer(
        r"\\crefname\s*\{([^{}]+)\}\s*\{([^{}]+)\}\s*\{([^{}]+)\}", text
    ):
        cref_names[match.group(1).strip()] = match.group(2).strip()

    raw_specs: list[tuple[str, str | None, str, str | None]] = []
    pattern = re.compile(
        r"\\newtheorem\s*\{([^{}]+)\}\s*"
        r"(?:\[([^\]]+)\])?\s*"
        r"\{([^{}]+)\}\s*"
        r"(?:\[([^\]]+)\])?"
    )
    for match in pattern.finditer(text):
        environment = match.group(1).strip()
        shared_counter = match.group(2).strip() if match.group(2) else None
        printed_name = match.group(3).strip()
        parent = match.group(4).strip() if match.group(4) else None
        raw_specs.append((environment, shared_counter, printed_name, parent))

    specs: dict[str, TheoremSpec] = {}
    for environment, shared_counter, printed_name, parent in raw_specs:
        counter = shared_counter or environment
        specs[environment] = TheoremSpec(
            environment=environment,
            printed_name=printed_name,
            counter=counter,
            parent=parent,
            reference_name=cref_names.get(environment, printed_name),
        )
    return specs


def patch_optional_theorem_titles(
    text: str, environments: Iterable[str], marker_counter: list[int]
) -> str:
    alternatives = "|".join(
        re.escape(environment)
        for environment in sorted(environments, key=len, reverse=True)
    )
    if not alternatives:
        return text
    pattern = re.compile(
        rf"\\begin\s*\{{({alternatives})\}}\s*\[([^\]\n]*)\]"
    )

    def replacement(match: re.Match[str]) -> str:
        marker_counter[0] += 1
        marker = f"{marker_counter[0]:06d}"
        environment = match.group(1)
        title = match.group(2)
        return (
            rf"\begin{{{environment}}}"
            rf"\label{{{TITLE_MARKER_PREFIX}{marker}}}"
            rf"\textbf{{{TITLE_START_PREFIX}{marker} {title} "
            rf"{TITLE_END_PREFIX}{marker}}}\par "
        )

    return pattern.sub(replacement, text)


def scoped_term_key(directory: Path, key: str) -> str:
    relative = directory.relative_to(PROJECT_ROOT).as_posix()
    digest = hashlib.sha1(relative.encode("utf-8")).hexdigest()[:10]
    return f"webscope-{digest}-{key}"


def patch_scoped_glossary_terms(
    text: str,
    source: Path,
    glossary: dict[str, Term],
    terms_by_directory: dict[Path, dict[str, Term]],
    conflicting_keys: set[str],
) -> str:
    if not conflicting_keys:
        return text

    def replacement(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in conflicting_keys:
            return match.group(0)
        directory = source.parent
        while is_inside(directory, PROJECT_ROOT):
            local_term = terms_by_directory.get(directory, {}).get(key)
            if local_term is not None:
                synthetic_key = scoped_term_key(directory, key)
                glossary[synthetic_key] = Term(
                    key=synthetic_key,
                    english=local_term.english,
                    chinese=local_term.chinese,
                    source=local_term.source,
                )
                return rf"\gls{{{synthetic_key}}}"
            if directory == PROJECT_ROOT:
                break
            directory = directory.parent
        return match.group(0)

    return re.sub(r"\\gls\s*\{([^{}]+)\}", replacement, text)


def patch_custom_math_environments(text: str) -> str:
    text = re.sub(r"\\begin\s*\{inequality\*\}", r"\\begin{equation*}", text)
    text = re.sub(r"\\end\s*\{inequality\*\}", r"\\end{equation*}", text)
    text = re.sub(r"\\begin\s*\{inequality\}", r"\\begin{equation}", text)
    text = re.sub(r"\\end\s*\{inequality\}", r"\\end{equation}", text)
    # Pandoc already appends the proof-ending square in HTML. MathJax does not
    # implement amsthm's placement-only \qedhere command and otherwise renders
    # it as a red error.
    text = text.replace(r"\qedhere", "")
    return text


def replace_algorithm_inline_macros(text: str) -> str:
    def replace_braced_macro(
        value: str,
        macro: str,
        replacement: Any,
        argument_count: int = 1,
    ) -> str:
        pattern = re.compile(rf"\\{re.escape(macro)}\b")
        result: list[str] = []
        cursor = 0
        while True:
            match = pattern.search(value, cursor)
            if match is None:
                result.append(value[cursor:])
                break
            result.append(value[cursor : match.start()])
            position = match.end()
            arguments: list[str] = []
            try:
                for _ in range(argument_count):
                    position = skip_space(value, position)
                    argument, position = read_balanced(
                        value, position, "{", "}"
                    )
                    arguments.append(argument)
            except ValueError:
                result.append(value[match.start() : match.end()])
                cursor = match.end()
                continue
            result.append(replacement(arguments, value, match.start()))
            cursor = position
        return "".join(result)

    text = replace_braced_macro(
        text,
        "Comment",
        lambda arguments, _value, _position: (
            rf"\textit{{（{arguments[0]}）}}"
        ),
    )

    def replace_call(
        arguments: list[str], value: str, position: int
    ) -> str:
        unescaped_dollars = len(
            re.findall(r"(?<!\\)\$", value[:position])
        )
        name, parameters = arguments
        if unescaped_dollars % 2:
            return (
                rf"\operatorname{{{name}}}\!\left("
                rf"{parameters}\right)"
            )
        return rf"\textsc{{{name}}}({parameters})"

    text = replace_braced_macro(
        text,
        "Call",
        replace_call,
        argument_count=2,
    )
    return text.replace(r"\Return", r"\textbf{return}")


def convert_algorithmic_body(text: str) -> str:
    command_pattern = re.compile(
        r"^[ \t]*\\(?P<command>"
        r"Statex|State|Require|Ensure|ForAll|For|EndFor|"
        r"If|ElsIf|Else|EndIf|While|EndWhile|Repeat|Until|"
        r"Function|EndFunction|Procedure|EndProcedure|"
        r"Loop|EndLoop|Comment"
        r")\b",
        flags=re.MULTILINE,
    )
    matches = list(command_pattern.finditer(text))
    if not matches:
        content = replace_algorithm_inline_macros(text).strip()
        if not content:
            return ""
        return (
            r"\begin{enumerate}" "\n"
            rf"\item \textbf{{{ALGORITHM_COMMAND_PREFIX}STATE}} "
            f"{content}\n"
            r"\end{enumerate}"
        )

    def marker(kind: str) -> str:
        return rf"\textbf{{{ALGORITHM_COMMAND_PREFIX}{kind.upper()}}}"

    def item(kind: str, content: str = "") -> str:
        content = replace_algorithm_inline_macros(content).strip()
        suffix = f" {content}" if content else ""
        return rf"\item {marker(kind)}{suffix}"

    def braced_arguments(
        value: str, count: int
    ) -> tuple[list[str], str]:
        position = 0
        arguments: list[str] = []
        try:
            for _ in range(count):
                position = skip_space(value, position)
                argument, position = read_balanced(
                    value, position, "{", "}"
                )
                arguments.append(argument)
        except ValueError:
            return [], value
        return arguments, value[position:]

    output = [r"\begin{enumerate}"]
    stack: list[str] = []
    prefix = replace_algorithm_inline_macros(
        text[: matches[0].start()]
    ).strip()
    if prefix:
        output.append(item("state", prefix))

    opening_commands = {
        "For": ("for", "for", "do"),
        "ForAll": ("for", "for all", "do"),
        "If": ("if", "if", "then"),
        "While": ("while", "while", "do"),
        "Function": ("function", "function", ""),
        "Procedure": ("procedure", "procedure", ""),
        "Loop": ("loop", "loop", ""),
    }
    ending_commands = {
        "EndFor": ("for", "end for"),
        "EndIf": ("if", "end if"),
        "EndWhile": ("while", "end while"),
        "EndFunction": ("function", "end function"),
        "EndProcedure": ("procedure", "end procedure"),
        "EndLoop": ("loop", "end loop"),
    }

    for index, match in enumerate(matches):
        command = match.group("command")
        segment_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )
        remainder = text[match.end() : segment_end]

        if command in {"Require", "Ensure"}:
            label = "输入：" if command == "Require" else "输出："
            output.append(
                item(command.lower(), rf"\textbf{{{label}}} {remainder}")
            )
            continue
        if command in {"State", "Statex"}:
            output.append(item(command.lower(), remainder))
            continue
        if command == "Comment":
            arguments, tail = braced_arguments(remainder, 1)
            content = (
                rf"\textit{{（{arguments[0]}）}} {tail}"
                if arguments
                else remainder
            )
            output.append(item("comment", content))
            continue
        if command == "Repeat":
            output.append(item("repeat", r"\textbf{repeat}"))
            output.append(r"\begin{enumerate}")
            stack.append("repeat")
            continue
        if command == "Until":
            arguments, tail = braced_arguments(remainder, 1)
            if stack:
                output.append(r"\end{enumerate}")
                stack.pop()
            condition = (
                f"{arguments[0]} {tail}" if arguments else remainder
            )
            output.append(
                item(
                    "until",
                    rf"\textbf{{until}} {condition}",
                )
            )
            continue
        if command in {"ElsIf", "Else"}:
            if stack and stack[-1] == "if":
                output.append(r"\end{enumerate}")
            if command == "ElsIf":
                arguments, tail = braced_arguments(remainder, 1)
                condition = arguments[0] if arguments else remainder
                content = (
                    rf"\textbf{{else if}} {condition} "
                    rf"\textbf{{then}} {tail}"
                )
                kind = "elsif"
            else:
                content = rf"\textbf{{else}} {remainder}"
                kind = "else"
            output.append(item(kind, content))
            if stack and stack[-1] == "if":
                output.append(r"\begin{enumerate}")
            continue
        if command in opening_commands:
            stack_kind, opening_label, ending_label = opening_commands[
                command
            ]
            argument_count = 2 if command in {"Function", "Procedure"} else 1
            arguments, tail = braced_arguments(
                remainder, argument_count
            )
            if command in {"Function", "Procedure"} and len(arguments) == 2:
                principal = rf"\textsc{{{arguments[0]}}}({arguments[1]})"
            elif arguments:
                principal = arguments[0]
            else:
                principal = remainder
                tail = ""
            content = rf"\textbf{{{opening_label}}} {principal}"
            if ending_label:
                content += rf" \textbf{{{ending_label}}}"
            content += f" {tail}"
            output.append(item(stack_kind, content))
            output.append(r"\begin{enumerate}")
            stack.append(stack_kind)
            continue
        if command in ending_commands:
            stack_kind, label = ending_commands[command]
            if stack:
                output.append(r"\end{enumerate}")
                stack.pop()
            output.append(
                item(stack_kind + "-end", rf"\textbf{{{label}}} {remainder}")
            )
            continue

        output.append(item("state", remainder))

    while stack:
        output.append(r"\end{enumerate}")
        stack.pop()
    output.append(r"\end{enumerate}")
    return "\n".join(output)


def patch_algorithm_environments(
    text: str, marker_counter: list[int]
) -> str:
    algorithm_pattern = re.compile(
        r"^[ \t]*\\begin\s*\{algorithm\}(?:\s*\[[^\]]*\])?"
        r"(?P<body>.*?)"
        r"^[ \t]*\\end\s*\{algorithm\}",
        flags=re.DOTALL | re.MULTILINE,
    )
    algorithmic_pattern = re.compile(
        r"^[ \t]*\\begin\s*\{algorithmic\}(?:\s*\[[^\]]*\])?"
        r"(?P<body>.*?)"
        r"^[ \t]*\\end\s*\{algorithmic\}",
        flags=re.DOTALL | re.MULTILINE,
    )

    def replace_caption(body: str, marker: str) -> str:
        match = re.search(r"\\caption\b", body)
        if match is None:
            return body
        position = skip_space(body, match.end())
        if position < len(body) and body[position] == "[":
            try:
                _, position = read_balanced(body, position, "[", "]")
                position = skip_space(body, position)
            except ValueError:
                return body
        try:
            caption, end = read_balanced(body, position, "{", "}")
        except ValueError:
            return body
        replacement = (
            rf"\textbf{{{ALGORITHM_TITLE_START_PREFIX}{marker} "
            rf"{caption} {ALGORITHM_TITLE_END_PREFIX}{marker}}}\par"
        )
        return body[: match.start()] + replacement + body[end:]

    def replacement(match: re.Match[str]) -> str:
        marker_counter[0] += 1
        marker = f"{marker_counter[0]:06d}"
        body = replace_caption(match.group("body"), marker)
        body = re.sub(
            r"\\label\s*\{([^{}]+)\}",
            r"\\hypertarget{\1}{}",
            body,
        )
        body = algorithmic_pattern.sub(
            lambda algorithmic: (
                r"\begin{algorithmic}" "\n"
                + convert_algorithmic_body(algorithmic.group("body"))
                + "\n"
                + r"\end{algorithmic}"
            ),
            body,
        )
        return (
            r"\begin{algorithm}" "\n"
            + body.strip()
            + "\n"
            + r"\end{algorithm}"
        )

    return algorithm_pattern.sub(replacement, text)


def render_tikz_image(
    tikz_source: str,
    source: Path,
    picture_index: int,
) -> Path:
    relative_source = source.relative_to(PROJECT_ROOT).as_posix()
    digest = hashlib.sha1(
        (
            "tikz-png-v1\n"
            + relative_source
            + f"\n{picture_index}\n"
            + tikz_source
        ).encode("utf-8")
    ).hexdigest()[:16]
    filename = f"tikz-{digest}.png"
    cached = TIKZ_CACHE_DIR / filename
    destination = STAGED_SOURCE_DIR / "_tikz" / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    if cached.is_file():
        shutil.copy2(cached, destination)
        return Path("_tikz") / filename

    xelatex = shutil.which("xelatex")
    ghostscript = shutil.which("gs")
    sips = shutil.which("sips")
    if xelatex is None or (ghostscript is None and sips is None):
        fail(
            "TikZ 转换需要 xelatex，以及 gs 或 sips；"
            "请确认 TeX Live 的可执行目录已加入 PATH。"
        )

    TIKZ_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = TIKZ_WORK_DIR / digest
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    wrapper = work_dir / "picture.tex"
    wrapper.write_text(
        "\n".join(
            [
                r"\documentclass[tikz,border=5pt]{standalone}",
                r"\usepackage[UTF8,fontset=fandol]{ctex}",
                r"\usepackage{amsmath,amssymb,mathtools}",
                r"\usepackage{tikz}",
                (
                    r"\usetikzlibrary{positioning,fit,calc,arrows.meta,"
                    r"shapes.geometric,shapes.misc,3d,matrix,"
                    r"decorations.pathreplacing}"
                ),
                r"\usepackage{pgfplots}",
                r"\pgfplotsset{compat=1.18}",
                r"\begin{document}",
                tikz_source.strip(),
                r"\end{document}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    latex_result = subprocess.run(
        [
            xelatex,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-no-shell-escape",
            wrapper.name,
        ],
        cwd=work_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    if latex_result.returncode != 0:
        if latex_result.stdout.strip():
            print(latex_result.stdout.rstrip(), file=sys.stderr)
        if latex_result.stderr.strip():
            print(latex_result.stderr.rstrip(), file=sys.stderr)
        fail(
            f"TikZ 编译失败：{relative_source} "
            f"（第 {picture_index} 幅）"
        )

    if ghostscript is not None:
        conversion_command = [
            ghostscript,
            "-q",
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-dUseCropBox",
            "-sDEVICE=pngalpha",
            "-r300",
            "-dTextAlphaBits=4",
            "-dGraphicsAlphaBits=4",
            f"-sOutputFile={cached}",
            str(work_dir / "picture.pdf"),
        ]
    else:
        conversion_command = [
            str(sips),
            "-s",
            "format",
            "png",
            "--resampleWidth",
            "1600",
            str(work_dir / "picture.pdf"),
            "--out",
            str(cached),
        ]
    image_result = subprocess.run(
        conversion_command,
        cwd=work_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    if image_result.returncode != 0:
        if image_result.stdout.strip():
            print(image_result.stdout.rstrip(), file=sys.stderr)
        if image_result.stderr.strip():
            print(image_result.stderr.rstrip(), file=sys.stderr)
        fail(
            f"TikZ 转图片失败：{relative_source} "
            f"（第 {picture_index} 幅）"
        )
    shutil.copy2(cached, destination)
    return Path("_tikz") / filename


def patch_density_plots(
    text: str,
    source: Path,
    rendered_counter: list[int],
) -> str:
    """Replace PDF-only densityplot figures with web component markers."""
    pattern = re.compile(
        r"\\begin\s*\{densityplot\}\s*\{(?P<name>[a-z0-9-]+)\}"
        r".*?\\end\s*\{densityplot\}",
        flags=re.DOTALL,
    )

    def replacement(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in DENSITY_PLOT_NAMES:
            relative = source.relative_to(PROJECT_ROOT)
            fail(f"未知的密度图类型 {name!r}：{relative}")
        rendered_counter[0] += 1
        return f"\n\n{DENSITY_PLOT_MARKER_PREFIX}{name}\n\n"

    return pattern.sub(replacement, text)


def patch_tikz_pictures(
    text: str,
    source: Path,
    rendered_counter: list[int],
) -> str:
    pattern = re.compile(
        r"^(?P<indent>[ \t]*)"
        r"(?P<picture>\\begin\s*\{tikzpicture\}.*?"
        r"^[ \t]*\\end\s*\{tikzpicture\})",
        flags=re.DOTALL | re.MULTILINE,
    )
    picture_index = 0

    def replacement(match: re.Match[str]) -> str:
        nonlocal picture_index
        picture_index += 1
        rendered_counter[0] += 1
        target = render_tikz_image(
            match.group("picture"),
            source,
            picture_index,
        )
        return (
            match.group("indent")
            + rf"\includegraphics[width=0.92\linewidth]"
            + rf"{{{target.as_posix()}}}"
        )

    return pattern.sub(replacement, text)


def patch_main_for_full_book(text: str) -> str:
    """Enable every part and chapter include in the staged main.tex copy."""

    pattern = re.compile(
        r"^(?P<indent>[ \t]*)%+[ \t]*"
        r"(?P<command>\\(?:part|include)\s*\{(?P<value>[^{}]+)\})"
        r"(?P<trailing>[ \t]*)$",
        flags=re.MULTILINE,
    )

    def replacement(match: re.Match[str]) -> str:
        command = match.group("command")
        if command.startswith(r"\include"):
            target = PROJECT_ROOT / f"{match.group('value')}.tex"
            if not target.is_file():
                return match.group(0)
        return (
            match.group("indent")
            + command
            + match.group("trailing")
        )

    return pattern.sub(replacement, text)


def stage_sources(
    theorem_specs: dict[str, TheoremSpec],
    glossary: dict[str, Term],
    terms_by_directory: dict[Path, dict[str, Term]],
    conflicting_keys: set[str],
) -> None:
    clean_generated_directory(STAGED_SOURCE_DIR)
    clean_generated_directory(TIKZ_WORK_DIR)
    STAGED_SOURCE_DIR.mkdir(parents=True)
    marker_counter = [0]
    algorithm_marker_counter = [0]
    density_plot_counter = [0]
    tikz_counter = [0]
    todo_marker_counter = [0]
    table_marker_counter = [0]
    STAGED_LATEX_TABLES.clear()
    copied = 0
    copied_code_files: set[Path] = set()
    for source in sorted(PROJECT_ROOT.rglob("*.tex")):
        if is_inside(source, HTML_DIR):
            continue
        relative = source.relative_to(PROJECT_ROOT)
        destination = STAGED_SOURCE_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8")
        if source == MAIN_TEX:
            text = patch_main_for_full_book(text)
        text = patch_scoped_glossary_terms(
            text,
            source,
            glossary,
            terms_by_directory,
            conflicting_keys,
        )
        if source != SETTINGS_TEX:
            text = patch_todo_macros(text, todo_marker_counter)
        text = patch_latex_tables(text, table_marker_counter)
        text = patch_custom_math_environments(text)
        text = patch_algorithm_environments(
            text, algorithm_marker_counter
        )
        text = patch_density_plots(
            text,
            source,
            density_plot_counter,
        )
        text = patch_tikz_pictures(
            text,
            source,
            tikz_counter,
        )
        text = patch_optional_theorem_titles(
            text, theorem_specs.keys(), marker_counter
        )
        destination.write_text(text, encoding="utf-8")
        for match in re.finditer(
            r"\\inputminted(?:\s*\[[^\]]*\])?\s*"
            r"\{[^{}]+\}\s*\{([^{}]+)\}",
            text,
        ):
            requested = Path(match.group(1))
            candidates = [
                PROJECT_ROOT / requested,
                source.parent / requested,
            ]
            code_source = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.is_file()
                    and is_inside(candidate, PROJECT_ROOT)
                ),
                None,
            )
            if code_source is None:
                continue
            code_relative = code_source.relative_to(PROJECT_ROOT)
            code_destination = STAGED_SOURCE_DIR / code_relative
            code_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(code_source, code_destination)
            copied_code_files.add(code_relative)
        copied += 1
    log(
        f"已暂存 {copied} 个 TeX 文件、"
        f"{len(copied_code_files)} 个代码文件，"
        f"标记 {marker_counter[0]} 个环境标题、"
        f"{algorithm_marker_counter[0]} 个算法，"
        f"{density_plot_counter[0]} 幅交互密度图、"
        f"转换 {tikz_counter[0]} 幅 TikZ 图片、"
        f"转换 {table_marker_counter[0]} 张 LaTeX 表格、"
        f"保留 {todo_marker_counter[0]} 条项目批注"
    )


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
    ) -> None:
        self.theorem_specs = theorem_specs
        self.glossary = glossary
        self.glossary_catalog = glossary_catalog
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
                    table = STAGED_LATEX_TABLES.get(table_match.group(1))
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
            block["c"] = self.process_child_block_lists(block.get("c"))
            result.append(block)
        return result

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
        "pandoc",
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


def yaml_quote(value: str) -> str:
    return json.dumps(" ".join(value.split()), ensure_ascii=False)


def book_contact_email() -> str:
    text = strip_tex_comments(SETTINGS_TEX.read_text(encoding="utf-8"))
    match = re.search(
        r"\bEmail\s*:\s*"
        r"([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else ""


def quarto_date(value: str) -> str:
    normalized = " ".join(value.split())
    chinese = re.fullmatch(
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        normalized,
    )
    if chinese:
        year, month, day = map(int, chinese.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        return normalized
    return ""


def load_site_metadata() -> dict[str, str]:
    if not SITE_META.is_file():
        fail(f"缺少站点元数据：{SITE_META.relative_to(PROJECT_ROOT)}")
    try:
        metadata = json.loads(SITE_META.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"站点元数据不是有效 JSON：{error}")
    required = ("first_published", "content_updated", "repository")
    for key in required:
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            fail(f"site-meta.json 缺少字符串字段 {key!r}")
    for key in ("first_published", "content_updated"):
        try:
            calendar_date.fromisoformat(metadata[key])
        except ValueError:
            fail(f"site-meta.json 的 {key} 必须使用 YYYY-MM-DD")
    repository = metadata["repository"].strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        fail("site-meta.json 的 repository 必须写成 owner/repository")
    owner, repository_name = repository.split("/", 1)
    metadata["repository"] = repository
    metadata["github_url"] = f"https://github.com/{repository}"
    metadata["site_url"] = (
        f"https://{owner.lower()}.github.io/{repository_name}/"
    )
    return metadata


def load_chapter_progress() -> dict[str, int | None]:
    if not CHAPTER_PROGRESS.is_file():
        fail(f"缺少章节进度文件：{CHAPTER_PROGRESS.relative_to(PROJECT_ROOT)}")
    try:
        progress = json.loads(CHAPTER_PROGRESS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"章节进度文件不是有效 JSON：{error}")
    if not isinstance(progress, dict):
        fail("chapter-progress.json 顶层必须是对象")
    result: dict[str, int | None] = {}
    for key, value in progress.items():
        if not isinstance(key, str):
            fail("chapter-progress.json 的章节键必须是字符串")
        if value is not None and (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 100
        ):
            fail(f"章节 {key!r} 的完成度必须是 0–100 的整数或 null")
        result[key] = value
    return result


def load_notation_catalog() -> dict[str, Any]:
    if not NOTATION_CATALOG.is_file():
        fail(
            "缺少 notation 规范："
            f"{NOTATION_CATALOG.relative_to(PROJECT_ROOT)}"
        )
    try:
        catalog = json.loads(NOTATION_CATALOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"notation catalog 不是有效 JSON：{error}")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("notation-catalog.json 必须包含非空 entries 列表")
    required = ("symbol", "name", "meaning", "category", "scope")
    seen_symbols: set[tuple[str, str]] = set()
    seen_identifiers: set[str] = set()
    for list_key in ("principles", "category_order"):
        value = catalog.get(list_key, [])
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            fail(f"notation-catalog.json 的 {list_key} 必须是字符串列表")
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            fail(f"notation entry {index} 必须是对象")
        for key in required:
            if key == "scope":
                if (
                    not isinstance(entry.get(key), list)
                    or not entry[key]
                    or not all(
                        isinstance(item, str) and item.strip()
                        for item in entry[key]
                    )
                ):
                    fail(f"notation entry {index} 的 scope 必须是非空列表")
            elif not isinstance(entry.get(key), str) or not entry[key].strip():
                fail(f"notation entry {index} 缺少字符串字段 {key!r}")
        identity = (entry["category"], entry["symbol"])
        if identity in seen_symbols:
            fail(f"notation catalog 重复条目：{identity}")
        seen_symbols.add(identity)
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[a-z][a-z0-9-]*", identifier
        ):
            fail(f"notation entry {index} 缺少稳定的 id（小写字母、数字、连字符）")
        if identifier in seen_identifiers:
            fail(f"notation catalog 重复 id：{identifier}")
        seen_identifiers.add(identifier)
        convention = entry.get("convention", "")
        if convention and not isinstance(convention, str):
            fail(f"notation entry {index} 的 convention 必须是字符串")
        render_tex = entry.get("render_tex", "")
        if render_tex and not isinstance(render_tex, str):
            fail(f"notation entry {index} 的 render_tex 必须是字符串")
        for list_key in ("avoid", "sources"):
            value = entry.get(list_key, [])
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                fail(f"notation entry {index} 的 {list_key} 必须是字符串列表")
    return catalog


def recent_git_commits(limit: int = 3) -> list[dict[str, str]]:
    result = subprocess.run(
        [
            "git",
            "log",
            f"-{limit}",
            "--date=short",
            "--format=%H%x1f%h%x1f%ad%x1f%s",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    commits: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split("\x1f", 3)
        if len(fields) != 4:
            continue
        full_hash, short_hash, commit_date, subject = fields
        commits.append(
            {
                "hash": full_hash,
                "short_hash": short_hash,
                "date": commit_date,
                "subject": subject,
            }
        )
    return commits


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
    return PAGE_SLUGS.get(normalized, f"page-{page_number:03d}")


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


def write_qmd_page(
    page: QuartoPage,
    document: dict[str, Any],
    chapter_progress: dict[str, int | None],
) -> None:
    destination = QUARTO_PROJECT_DIR / page.source_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    page_document = {
        "pandoc-api-version": document["pandoc-api-version"],
        "meta": {},
        "blocks": page.blocks,
    }
    markdown = run(
        [
            "pandoc",
            "--from=json",
            "--to=markdown+fenced_divs+raw_html+tex_math_dollars",
            "--wrap=none",
        ],
        cwd=PROJECT_ROOT,
        input_text=json.dumps(page_document, ensure_ascii=False),
    )

    list_marker_pattern = (
        r"^(?P<indent>[ \t]*)(?:\d+[.)]|[-+*])(?P<space>[ \t]+)"
    )

    def list_continuation_indentation(line: str) -> str:
        marker = re.match(list_marker_pattern, line)
        if marker:
            return (
                marker.group("indent")
                + " " * (
                    len(marker.group(0))
                    - len(marker.group("indent"))
                )
            )
        return line[: len(line) - len(line.lstrip())]

    def format_display_math(match: re.Match[str]) -> str:
        source = textwrap.dedent(match.group("source")).strip()
        line_start = markdown.rfind("\n", 0, match.start()) + 1
        line_before_match = markdown[line_start : match.start()]
        line_prefix = line_before_match + match.group("leading")
        is_block = not line_prefix.strip()

        if is_block:
            indentation = ""
        else:
            indentation = list_continuation_indentation(line_prefix)

        def indent_lines(value: str) -> str:
            return "\n".join(
                indentation + line if line else indentation
                for line in value.splitlines()
            )

        environment = re.fullmatch(
            r"\\begin\{([A-Za-z*]+)\}.*\\end\{\1\}",
            source,
            flags=re.DOTALL,
        )
        if environment:
            # Quarto/Pandoc already recognizes AMS display environments. Keeping
            # an additional pair of dollar delimiters makes those dollars appear
            # literally around the rendered formula.
            math_block = indent_lines(source)
        else:
            math_block = (
                f"{indentation}$$\n"
                f"{indent_lines(source)}\n"
                f"{indentation}$$"
            )

        if not is_block:
            return (
                f"\n\n{math_block}\n\n"
                f"{indentation}"
            )
        return math_block

    markdown = re.sub(
        r"(?P<leading>[ \t]*)\$\$(?P<source>.*?)\$\$(?P<trailing>[ \t]*)",
        format_display_math,
        markdown,
        flags=re.DOTALL | re.MULTILINE,
    )

    lines = markdown.splitlines()
    list_levels: list[int] = []
    in_code_fence = False
    for line_index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence or not stripped:
            continue

        list_marker = re.match(list_marker_pattern, line)
        if list_marker:
            marker_level = len(
                list_marker.group("indent").expandtabs(4)
            )
            while list_levels and marker_level < list_levels[-1]:
                list_levels.pop()
            if not list_levels or marker_level > list_levels[-1]:
                list_levels.append(marker_level)
            continue

        leading = line[: len(line) - len(line.lstrip())]
        if not leading:
            list_levels.clear()
        elif not list_levels:
            # Pandoc can retain source-code indentation after display math even
            # when the paragraph is not in a Markdown list. Four leading spaces
            # would turn that paragraph and subsequent formulas into code.
            lines[line_index] = line.lstrip()

    index = 0
    while index < len(lines):
        opening = re.match(
            r"^[ \t]*(?:"
            r"(?P<dollars>\$\$)|"
            r"\\begin\{(?P<environment>"
            r"equation\*?|align\*?|gather\*?|multline\*?"
            r")\}"
            r")[ \t]*$",
            lines[index],
        )
        if not opening:
            index += 1
            continue

        if opening.group("dollars"):
            closing_pattern = re.compile(r"^[ \t]*\$\$[ \t]*$")
        else:
            environment = opening.group("environment")
            closing_pattern = re.compile(
                rf"^[ \t]*\\end\{{{re.escape(environment)}\}}[ \t]*$"
            )
        closing = index + 1
        while closing < len(lines) and not closing_pattern.match(lines[closing]):
            closing += 1
        if closing >= len(lines):
            index += 1
            continue

        previous = index - 1
        while previous >= 0 and not lines[previous].strip():
            previous -= 1
        indentation = (
            list_continuation_indentation(lines[previous])
            if previous >= 0
            else ""
        )
        if previous >= 0 and not re.match(
            list_marker_pattern,
            lines[previous],
        ):
            previous_indentation = lines[previous][
                : len(lines[previous]) - len(lines[previous].lstrip())
            ]
            indentation = previous_indentation

        block = textwrap.dedent(
            "\n".join(lines[index : closing + 1])
        ).splitlines()
        lines[index : closing + 1] = [
            indentation + line if line else indentation
            for line in block
        ]
        index = closing + 1
    markdown = "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")

    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    page_slug = page.source_path.stem
    if page_slug in chapter_progress:
        value = chapter_progress[page_slug]
        if value is None:
            value_label = "待填写"
            state_class = "chapter-progress--unset"
            progress_attributes = 'aria-label="本章完成度尚未填写"'
            progress_width = 0
        else:
            value_label = f"{value}%"
            state_class = ""
            progress_attributes = (
                'role="progressbar" aria-label="本章完成度" '
                f'aria-valuemin="0" aria-valuemax="100" aria-valuenow="{value}"'
            )
            progress_width = value
        progress_markup = (
            f'<div class="chapter-progress {state_class}" role="region" '
            f'aria-label="当前章节完成度" data-chapter="{page_slug}" '
            f'data-progress="{value_label}">\n'
            '<div class="chapter-progress__heading">'
            '<span class="chapter-progress__eyebrow">CHAPTER STATUS</span>'
            '<span class="chapter-progress__label">编写进度</span>'
            f'<strong>{value_label}</strong>'
            '<a href="../project-status.html">查看全书进度</a></div>\n'
            f'<div class="chapter-progress__track" {progress_attributes}>'
            f'<span style="--chapter-progress: {progress_width}%"></span></div>\n'
            "</div>"
        )
        markdown_lines = markdown.splitlines()
        header_index = next(
            (
                index
                for index, line in enumerate(markdown_lines)
                if line.startswith("# ")
            ),
            None,
        )
        if header_index is not None:
            markdown_lines[header_index + 1 : header_index + 1] = [
                "",
                progress_markup,
                "",
            ]
            markdown = "\n".join(markdown_lines) + "\n"
    if page.source_path.name == "references.qmd":
        markdown = "---\nnocite: '@*'\n---\n\n" + markdown.lstrip()
    destination.write_text(markdown, encoding="utf-8")


def github_issue_url(
    metadata: dict[str, str],
    *,
    title: str,
    body: str,
    labels: str = "",
) -> str:
    query: dict[str, str] = {"title": title, "body": body}
    if labels:
        query["labels"] = labels
    return f"{metadata['github_url']}/issues/new?{urlencode(query)}"


def render_site_timeline(metadata: dict[str, str]) -> str:
    return (
        '<dl class="site-timeline" aria-label="项目时间线">'
        '<div><dt>首次发布</dt>'
        f'<dd><time datetime="{metadata["first_published"]}">'
        f'{metadata["first_published"]}</time></dd></div>'
        '<div><dt>最近内容更新</dt>'
        f'<dd><time datetime="{metadata["content_updated"]}">'
        f'{metadata["content_updated"]}</time></dd></div>'
        '<div><dt>网站构建</dt>'
        f'<dd><time datetime="{calendar_date.today().isoformat()}">'
        f'{calendar_date.today().isoformat()}</time></dd></div></dl>'
    )


def render_recent_commits(
    metadata: dict[str, str], commits: list[dict[str, str]]
) -> str:
    if commits:
        items = "".join(
            '<li><a href="'
            + metadata["github_url"]
            + "/commit/"
            + html.escape(commit["hash"], quote=True)
            + '"><code>'
            + html.escape(commit["short_hash"])
            + "</code><span>"
            + html.escape(commit["subject"])
            + "</span><time datetime=\""
            + html.escape(commit["date"], quote=True)
            + '\">'
            + html.escape(commit["date"])
            + "</time></a></li>"
            for commit in commits
        )
    else:
        items = '<li class="home-commit-empty">当前构建无法读取本地提交记录。</li>'
    return (
        '<div class="home-update-heading"><span class="home-live-badge">'
        '<i aria-hidden="true"></i>持续更新中</span>'
        f'<a href="{metadata["github_url"]}/commits/main/">查看全部提交</a></div>'
        f'<ol class="home-commits">{items}</ol>'
    )


def render_github_actions(metadata: dict[str, str]) -> str:
    error_url = github_issue_url(
        metadata,
        title="[错误报告] ",
        body="请描述发现的问题，并附上相关页面地址或章节位置。\n\n问题描述：\n\n页面地址：",
        labels="bug",
    )
    suggestion_url = github_issue_url(
        metadata,
        title="[内容建议] ",
        body="请说明建议修改或补充的内容，并附上相关章节位置。\n\n建议内容：\n\n相关章节：",
        labels="content",
    )
    actions = [
        ("bi-code-slash", "查看源代码", metadata["github_url"]),
        ("bi-bug", "报告错误", error_url),
        ("bi-chat-left-text", "提出内容建议", suggestion_url),
        ("bi-clock-history", "查看更新记录", f'{metadata["github_url"]}/commits/main/'),
    ]
    return '<nav class="github-actions" aria-label="GitHub 项目入口">' + "".join(
        f'<a href="{html.escape(url, quote=True)}"><i class="bi {icon}" '
        f'aria-hidden="true"></i><span>{label}</span>'
        '<i class="bi bi-arrow-up-right" aria-hidden="true"></i></a>'
        for icon, label, url in actions
    ) + "</nav>"


def project_statistics(
    transformer: BookTransformer,
    pages: list[QuartoPage],
) -> list[tuple[str, int, str]]:
    chapter_count = sum(
        page.part not in {None, "中英术语表"} for page in pages
    )
    counts = transformer.environment_counts
    return [
        ("正文章节", chapter_count, "chapter"),
        ("定义", counts.get("definition", 0), "definition"),
        ("定理", counts.get("theorem", 0), "theorem"),
        ("性质", counts.get("property", 0), "property"),
        ("引理", counts.get("lemma", 0), "lemma"),
        ("推论", counts.get("corollary", 0), "corollary"),
        ("证明", transformer.proof_count, "proof"),
        ("算法", transformer.content_counts.get("algorithm", 0), "algorithm"),
        ("行间公式", transformer.content_counts.get("display-math", 0), "equation"),
        ("交互图", transformer.content_counts.get("interactive-density-plot", 0), "plot"),
        ("中英术语", transformer.glossary_entry_count, "glossary"),
    ]


def render_project_snapshot(statistics: list[tuple[str, int, str]]) -> str:
    featured = [
        item
        for item in statistics
        if item[2] in {"definition", "theorem", "property", "proof"}
    ]
    return '<div class="project-snapshot">' + "".join(
        f'<div><strong>{value}</strong><span>{html.escape(label)}</span></div>'
        for label, value, _key in featured
    ) + '</div><a class="home-section-link" href="project-status.html">查看完整项目状态 <span aria-hidden="true">→</span></a>'


def render_statistics_grid(statistics: list[tuple[str, int, str]]) -> str:
    return '<div class="statistics-grid">' + "".join(
        f'<article class="statistic-card statistic-card--{key}">'
        f'<span>{html.escape(label)}</span><strong>{value}</strong></article>'
        for label, value, key in statistics
    ) + "</div>"


def render_progress_overview(
    pages: list[QuartoPage],
    progress: dict[str, int | None],
) -> str:
    groups: list[tuple[str, list[QuartoPage]]] = []
    group_lookup: dict[str, list[QuartoPage]] = {}
    displayed_progress = {
        key: value for key, value in progress.items() if key != "inequalities"
    }
    for page in pages:
        slug = page.source_path.stem
        if slug not in displayed_progress or page.part is None:
            continue
        part = page.part or "其他"
        if part not in group_lookup:
            group_lookup[part] = []
            groups.append((part, group_lookup[part]))
        group_lookup[part].append(page)
    sections: list[str] = []
    for part, group_pages in groups:
        rows: list[str] = []
        for page in group_pages:
            slug = page.source_path.stem
            value = displayed_progress[slug]
            label = "待填写" if value is None else f"{value}%"
            width = 0 if value is None else value
            state = " status-progress-row--unset" if value is None else ""
            title = re.sub(r"^第\s*\d+\s*章\s*", "", page_title(page)).strip()
            rows.append(
                f'<a class="status-progress-row{state}" '
                f'href="{page.source_path.with_suffix(".html").as_posix()}">'
                f'<span class="status-progress-row__title">{html.escape(title)}</span>'
                '<span class="status-progress-row__track" aria-hidden="true">'
                f'<i style="--chapter-progress: {width}%"></i></span>'
                f'<strong>{label}</strong></a>'
            )
        display_part = re.sub(
            r"^第\s*\d+\s*部分\s*", "", part
        ).strip()
        sections.append(
            f'<section class="status-part"><h2>{html.escape(display_part)}</h2>'
            + "".join(rows)
            + "</section>"
        )
    values = [
        value for value in displayed_progress.values() if value is not None
    ]
    average = round(sum(values) / len(values)) if values else None
    summary = (
        f"已填写 {len(values)} / {len(displayed_progress)} 章"
        + (f"，已填写章节平均完成度 {average}%" if average is not None else "")
    )
    return (
        f'<p class="status-progress-summary">{summary}</p>'
        '<div class="status-progress-groups">'
        + "".join(sections)
        + "</div>"
    )


def write_project_status_page(
    *,
    metadata: dict[str, str],
    commits: list[dict[str, str]],
    pages: list[QuartoPage],
    progress: dict[str, int | None],
    statistics: list[tuple[str, int, str]],
) -> None:
    content = "\n".join(
        [
            "---",
            "title: 项目状态",
            f"description: {yaml_quote('笔记维护时间、章节完成度与内容统计。')}",
            "---",
            "",
            ':::: {.project-status-page}',
            '::: {.status-section}',
            '<p class="status-kicker">MAINTENANCE</p>',
            "## 维护时间",
            "",
            render_site_timeline(metadata),
            render_recent_commits(metadata, commits),
            "",
            ":::",
            "",
            '::: {.status-section}',
            '<p class="status-kicker">PROGRESS</p>',
            "## 章节完成度",
            "",
            render_progress_overview(pages, progress),
            "",
            ":::",
            "",
            '::: {.status-section}',
            '<p class="status-kicker">CONTENT</p>',
            "## 笔记数据",
            "",
            render_statistics_grid(statistics),
            "",
            ":::",
            "",
            '::: {.status-section}',
            '<p class="status-kicker">CONTRIBUTE</p>',
            "## 参与维护",
            "",
            render_github_actions(metadata),
            "",
            ":::",
            "",
            "::::",
            "",
        ]
    )
    (QUARTO_PROJECT_DIR / "project-status.qmd").write_text(
        content, encoding="utf-8"
    )


def write_notation_page(catalog: dict[str, Any]) -> None:
    def raw_html_text(value: Any) -> str:
        """Escape text that Pandoc will encounter inside a raw HTML table.

        Pandoc still interprets Markdown punctuation in raw table cells.  Emit
        ASCII punctuation as numeric HTML entities so TeX operators, scripts,
        delimiters and literal code survive unchanged.  The browser decodes
        the entities before MathJax inspects the DOM.
        """
        return "".join(
            character
            if character.isalnum()
            or character.isspace()
            or ord(character) >= 128
            else f"&#{ord(character)};"
            for character in str(value)
        )

    entries = catalog["entries"]
    category_order = catalog.get("category_order", [])
    categories = list(category_order)
    categories.extend(
        category
        for category in dict.fromkeys(entry["category"] for entry in entries)
        if category not in categories
    )
    sections: list[str] = []
    for category in categories:
        rows: list[str] = []
        for entry in entries:
            if entry["category"] != category:
                continue
            source = raw_html_text(entry["symbol"])
            rendered = raw_html_text(entry.get("render_tex", entry["symbol"]))
            rows.append(
                f'<tr id="notation-{html.escape(entry["id"], quote=True)}">'
                f'<td class="notation-rendered">&#92;({rendered}&#92;)</td>'
                f'<td class="notation-source"><code>{source}</code></td>'
                f'<td class="notation-meaning"><strong>{raw_html_text(entry["name"])}</strong>'
                f'<p>{raw_html_text(entry["meaning"])}</p></td>'
                f'<td class="notation-scope">{raw_html_text("、".join(entry["scope"]))}</td>'
                '</tr>'
            )
        if rows:
            sections.append(
                f'## {category} {{.notation-section-title}}\n\n'
                '<table class="notation-table">'
                '<thead><tr><th>数学记号</th><th>LaTeX</th><th>含义</th><th>适用范围</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table>\n'
            )
    content = "\n".join(
        [
            "---",
            "title: 符号与记号说明",
            f"description: {yaml_quote('本书常用数学符号索引。')}",
            "---",
            "",
            '[$0$]{.notation-math-bootstrap aria-hidden="true"}',
            "",
            *sections,
            "",
        ]
    )
    (QUARTO_PROJECT_DIR / "notation.qmd").write_text(content, encoding="utf-8")


def write_quarto_config(
    document: dict[str, Any],
    pages: list[QuartoPage],
    transformer: BookTransformer,
    site_metadata: dict[str, str],
    chapter_progress: dict[str, int | None],
    notation_catalog: dict[str, Any],
) -> None:
    title = ast_plain_text(document["meta"].get("title", {})).strip()
    author = ast_plain_text(document["meta"].get("author", {})).strip()
    raw_date = ast_plain_text(document["meta"].get("date", {})).strip()
    date = quarto_date(raw_date)
    email = book_contact_email()
    title = title or "数学教材"
    commits = recent_git_commits()
    statistics = project_statistics(transformer, pages)
    write_project_status_page(
        metadata=site_metadata,
        commits=commits,
        pages=pages,
        progress=chapter_progress,
        statistics=statistics,
    )
    write_notation_page(notation_catalog)
    preface_href = next(
        (
            page.source_path.with_suffix(".html").as_posix()
            for page in pages
            if re.sub(r"^第\s*\d+\s*章\s*", "", page_title(page)).strip()
            == "前言"
        ),
        "chapters/preface.html",
    )
    glossary_href = next(
        (
            page.source_path.with_suffix(".html").as_posix()
            for page in pages
            if page.blocks and node_identifier(page.blocks[0]) == "glossary"
        ),
        "chapters/glossary.html",
    )
    chapter_count = sum(
        page.part not in {None, "中英术语表"} for page in pages
    )
    knowledge_parts: list[str] = []
    for page in pages:
        if page.part is None:
            continue
        part_title = re.sub(
            r"^第\s*\d+\s*部分\s*", "", page.part
        ).strip()
        if (
            part_title in {"中英术语表", "不等式"}
            or part_title in knowledge_parts
        ):
            continue
        knowledge_parts.append(part_title)

    index = [
        "---",
        f"title: {yaml_quote(title)}",
        f"description: {yaml_quote(SITE_DESCRIPTION)}",
    ]
    if author:
        if email:
            index.extend(
                [
                    "author:",
                    f"  - name: {yaml_quote(author)}",
                    f"    email: {yaml_quote(email)}",
                ]
            )
        else:
            index.append(f"author: {yaml_quote(author)}")
    if date:
        index.append(f"date: {yaml_quote(date)}")
        index.append("date-format: long")
    index.append(
        f"date-modified: {yaml_quote(calendar_date.today().isoformat())}"
    )
    home_content = (
        HOME_CONTENT.read_text(encoding="utf-8").strip()
        if HOME_CONTENT.exists()
        else "这是由项目中的 `main.tex` 自动生成的在线版本。"
    )
    home_content = (
        home_content.replace("__BOOK_EMAIL__", html.escape(email, quote=True))
        .replace("__BUILD_DATE__", calendar_date.today().isoformat())
        .replace("__BUILD_YEAR__", str(calendar_date.today().year))
        .replace("__PREFACE_HREF__", preface_href)
        .replace("__GLOSSARY_HREF__", glossary_href)
        .replace("__CHAPTER_COUNT__", str(chapter_count))
        .replace("__PART_COUNT__", str(len(knowledge_parts)))
        .replace("__SITE_TIMELINE__", render_site_timeline(site_metadata))
        .replace("__RECENT_COMMITS__", render_recent_commits(site_metadata, commits))
        .replace("__GITHUB_ACTIONS__", render_github_actions(site_metadata))
        .replace("__PROJECT_SNAPSHOT__", render_project_snapshot(statistics))
    )
    remaining_placeholders = sorted(set(re.findall(r"__[A-Z][A-Z_]+__", home_content)))
    if remaining_placeholders:
        fail("首页存在未替换占位符：" + "、".join(remaining_placeholders))
    index.extend(
        [
            "---",
            "",
            home_content,
        ]
    )
    if email and "textbook-home" not in home_content:
        index.extend(
            [
                "",
                f"联系邮箱：[{email}](mailto:{email})",
            ]
        )
    index.append("")
    (QUARTO_PROJECT_DIR / "index.qmd").write_text(
        "\n".join(index),
        encoding="utf-8",
    )

    chapter_lines = ["    - index.qmd"]
    current_part: str | None = None
    for page in pages:
        if page.part == "中英术语表":
            current_part = None
            chapter_lines.append(f"    - {page.source_path.as_posix()}")
            continue
        if page.part is None:
            current_part = None
            chapter_lines.append(f"    - {page.source_path.as_posix()}")
            continue
        if page.part != current_part:
            current_part = page.part
            chapter_lines.append(f"    - part: {yaml_quote(current_part)}")
            chapter_lines.append("      chapters:")
        chapter_lines.append(f"        - {page.source_path.as_posix()}")
    chapter_lines.extend(
        [
            "    - part: 项目",
            "      chapters:",
            "        - project-status.qmd",
            "        - notation.qmd",
        ]
    )

    hidden_sidebar_pages = [
        page.source_path.with_suffix(".html").name
        for page in pages
        if not page.sidebar_visible
    ]
    sidebar_rules = [
        "/* Generated by build.py: glossary letter pages stay searchable",
        "   without occupying the book sidebar. */",
    ]
    sidebar_rules.extend(
        (
            "#quarto-sidebar li.sidebar-item:has("
            "> .sidebar-item-container > "
            f'a.sidebar-link[href$="{filename}"]) {{ display: none; }}'
        )
        for filename in hidden_sidebar_pages
    )
    (QUARTO_PROJECT_DIR / "sidebar.css").write_text(
        "\n".join(sidebar_rules) + "\n",
        encoding="utf-8",
    )

    config = [
        "project:",
        "  type: book",
        "  output-dir: _site",
        "  resources:",
        "    - density-plots.js",
        "    - density-loader.js",
        "    - density-math.js",
        "    - density-probe.js",
        "    - formula-copy.js",
        "    - textbook-ui.js",
        "    - favicon.svg",
        "",
        "lang: zh",
        "date-format: long",
        f"bibliography: {yaml_quote('../../../ref.bib')}",
        f"csl: {yaml_quote('textbook.csl')}",
        "",
        "book:",
        f"  title: {yaml_quote(title)}",
        f"  description: {yaml_quote(SITE_DESCRIPTION)}",
        f"  site-url: {yaml_quote(site_metadata['site_url'])}",
        f"  repo-url: {yaml_quote(site_metadata['github_url'])}",
        "  favicon: favicon.svg",
    ]
    if author:
        if email:
            config.extend(
                [
                    "  author:",
                    f"    - name: {yaml_quote(author)}",
                    f"      email: {yaml_quote(email)}",
                ]
            )
        else:
            config.append(f"  author: {yaml_quote(author)}")
    if date:
        config.append(f"  date: {yaml_quote(date)}")
    config.extend(
        [
            "  search: true",
            "  page-navigation: true",
            "  sidebar:",
            "    style: docked",
            "    collapse-level: 2",
            "  chapters:",
            *chapter_lines,
            "",
            "format:",
            "  html:",
            "    theme:",
            "      light: cosmo",
            "      dark: darkly",
            "    include-in-header: theme-toggle.html",
            "    include-after-body:",
            "      - density-plots.html",
            "      - formula-copy.html",
            "    css:",
            "      - style.css",
            "      - sidebar.css",
            "    toc: true",
            "    toc-title: 本页目录",
            "    toc-depth: 3",
            "    number-sections: false",
            "    code-copy: true",
            "    code-overflow: wrap",
            "    smooth-scroll: true",
            "    link-external-newwindow: true",
            "    open-graph: true",
            "    twitter-card: true",
            "    html-math-method: mathjax",
            "    grid:",
            "      sidebar-width: 305px",
            "      body-width: 920px",
            "      margin-width: 230px",
            "      gutter-width: 1.4rem",
            "",
        ]
    )
    (QUARTO_PROJECT_DIR / "_quarto.yml").write_text(
        "\n".join(config),
        encoding="utf-8",
    )


def copy_quarto_resources(document: dict[str, Any]) -> None:
    image_paths: set[str] = set()

    def collect_images(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                collect_images(item)
            return
        if not isinstance(value, dict):
            return
        if value.get("t") is None:
            for item in value.values():
                collect_images(item)
            return
        if value.get("t") == "Image":
            target = value["c"][2][0]
            if target and not urlsplit(target).scheme:
                image_paths.add(target)
        if "c" in value:
            collect_images(value["c"])

    collect_images(document)
    for image_path in image_paths:
        candidates = [
            STAGED_SOURCE_DIR / image_path,
            PROJECT_ROOT / image_path,
        ]
        source = next(
            (
                candidate
                for candidate in candidates
                if candidate.exists() and candidate.is_file()
            ),
            None,
        )
        if source is None:
            continue
        destination = QUARTO_PROJECT_DIR / image_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(HTML_DIR / "style.css", QUARTO_PROJECT_DIR / "style.css")
    shutil.copy2(DENSITY_PLOT_SCRIPT, QUARTO_PROJECT_DIR / "density-plots.js")
    shutil.copy2(DENSITY_PLOT_INCLUDE, QUARTO_PROJECT_DIR / "density-plots.html")
    shutil.copy2(DENSITY_LOADER_SCRIPT, QUARTO_PROJECT_DIR / "density-loader.js")
    shutil.copy2(DENSITY_MATH_SCRIPT, QUARTO_PROJECT_DIR / "density-math.js")
    shutil.copy2(DENSITY_PROBE_SCRIPT, QUARTO_PROJECT_DIR / "density-probe.js")
    shutil.copy2(FORMULA_COPY_SCRIPT, QUARTO_PROJECT_DIR / "formula-copy.js")
    shutil.copy2(FORMULA_COPY_INCLUDE, QUARTO_PROJECT_DIR / "formula-copy.html")
    user_interface_version = hashlib.sha256(
        TEXTBOOK_UI_SCRIPT.read_bytes()
    ).hexdigest()[:12]
    theme_toggle = (HTML_DIR / "theme-toggle.html").read_text(encoding="utf-8")
    theme_toggle = theme_toggle.replace(
        "__TEXTBOOK_UI_VERSION__", user_interface_version
    )
    (QUARTO_PROJECT_DIR / "theme-toggle.html").write_text(
        theme_toggle,
        encoding="utf-8",
    )
    shutil.copy2(TEXTBOOK_UI_SCRIPT, QUARTO_PROJECT_DIR / "textbook-ui.js")
    shutil.copy2(FAVICON, QUARTO_PROJECT_DIR / "favicon.svg")
    shutil.copy2(BIBLIOGRAPHY_STYLE, QUARTO_PROJECT_DIR / "textbook.csl")


def load_computation_orders() -> dict[str, list[ComputationGroup]]:
    orders: dict[str, list[ComputationGroup]] = {}
    missing_results: list[Path] = []
    for order_path in sorted(PROJECT_ROOT.rglob("computations.order")):
        if is_inside(order_path, HTML_DIR):
            continue
        chapter_source = order_path.parent / "main.tex"
        if not chapter_source.is_file():
            fail(
                "computations.order 必须与包含 chapter 的 main.tex 放在同一目录："
                f"{order_path.relative_to(PROJECT_ROOT)}"
            )
        chapter_text = strip_tex_comments(
            chapter_source.read_text(encoding="utf-8")
        )
        chapter_match = re.search(
            r"\\chapter(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}",
            chapter_text,
        )
        if not chapter_match:
            fail(
                "找不到 computations.order 对应的 chapter："
                f"{chapter_source.relative_to(PROJECT_ROOT)}"
            )
        chapter_title = latex_to_plain(chapter_match.group(1)).strip()
        if chapter_title in orders:
            fail(f"章节 {chapter_title!r} 存在多个 computations.order")

        groups: list[ComputationGroup] = []
        current_title: str | None = None
        current_results: list[Path] = []

        def finish_group() -> None:
            nonlocal current_title, current_results
            if current_title is None:
                return
            if not current_results:
                fail(
                    f"计算案例 {current_title!r} 没有结果文件："
                    f"{order_path.relative_to(PROJECT_ROOT)}"
                )
            groups.append(
                ComputationGroup(
                    title=current_title,
                    result_paths=tuple(current_results),
                )
            )
            current_title = None
            current_results = []

        for line_number, raw_line in enumerate(
            order_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if not line or line.startswith("<!--"):
                continue
            if line.startswith("## "):
                finish_group()
                current_title = line[3:].strip()
                if not current_title:
                    fail(
                        f"空的计算案例标题：{order_path.relative_to(PROJECT_ROOT)}:"
                        f"{line_number}"
                    )
                continue
            if line.startswith("#"):
                continue
            if line.startswith("- "):
                if current_title is None:
                    fail(
                        f"结果路径必须位于二级标题之后："
                        f"{order_path.relative_to(PROJECT_ROOT)}:{line_number}"
                    )
                relative = Path(line[2:].strip())
                target = (order_path.parent / relative).resolve()
                if not is_inside(target, PROJECT_ROOT) or target.suffix.lower() != ".html":
                    fail(
                        f"计算结果必须是项目内的 HTML 文件："
                        f"{order_path.relative_to(PROJECT_ROOT)}:{line_number}"
                    )
                current_results.append(target)
                if not target.is_file():
                    missing_results.append(target)
                continue
            fail(
                f"无法识别 computations.order 中的内容："
                f"{order_path.relative_to(PROJECT_ROOT)}:{line_number}"
            )
        finish_group()
        if not groups:
            fail(f"没有计算案例：{order_path.relative_to(PROJECT_ROOT)}")
        orders[chapter_title] = groups

    if missing_results:
        details = "\n".join(
            f"  - {path.relative_to(PROJECT_ROOT)}"
            for path in missing_results
        )
        fail(
            "数值计算结果尚未生成。请先在各自的 Python/R 环境中渲染：\n"
            + details
        )
    return orders


def prefix_computation_identifiers(fragment: str, prefix: str) -> str:
    identifiers = set(
        re.findall(
            r"\bid\s*=\s*[\"']([^\"']+)[\"']",
            fragment,
            flags=re.IGNORECASE,
        )
    )

    def replace_id(match: re.Match[str]) -> str:
        return f'{match.group(1)}{match.group(2)}{prefix}{match.group(3)}{match.group(2)}'

    fragment = re.sub(
        r"(\bid\s*=\s*)([\"'])([^\"']+)(?:\2)",
        replace_id,
        fragment,
        flags=re.IGNORECASE,
    )

    def replace_fragment_link(match: re.Match[str]) -> str:
        identifier = match.group(3)
        if identifier not in identifiers:
            return match.group(0)
        return f'{match.group(1)}{match.group(2)}#{prefix}{identifier}{match.group(2)}'

    fragment = re.sub(
        r"(\bhref\s*=\s*)([\"'])#([^\"']+)(?:\2)",
        replace_fragment_link,
        fragment,
        flags=re.IGNORECASE,
    )
    for attribute in ("aria-labelledby", "aria-describedby", "for"):
        pattern = rf"(\b{attribute}\s*=\s*)([\"'])([^\"']+)(?:\2)"

        def replace_reference(match: re.Match[str]) -> str:
            values = " ".join(
                prefix + value if value in identifiers else value
                for value in match.group(3).split()
            )
            return f"{match.group(1)}{match.group(2)}{values}{match.group(2)}"

        fragment = re.sub(
            pattern,
            replace_reference,
            fragment,
            flags=re.IGNORECASE,
        )
    return fragment


def extract_computation_fragment(result_path: Path, prefix: str) -> str:
    markup = result_path.read_text(encoding="utf-8")
    main_match = re.search(
        r'<main\b(?=[^>]*\bid=["\']quarto-document-content["\'])[^>]*>'
        r"(.*?)</main>",
        markup,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if main_match:
        fragment = main_match.group(1)
    else:
        body_match = re.search(
            r"<body\b[^>]*>(.*?)</body>",
            markup,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not body_match:
            fail(
                "无法从计算结果中提取 HTML 正文："
                f"{result_path.relative_to(PROJECT_ROOT)}"
            )
        fragment = body_match.group(1)

    fragment = re.sub(
        r'<header\b(?=[^>]*\bid=["\']title-block-header["\'])[^>]*>'
        r".*?</header>",
        "",
        fragment,
        flags=re.IGNORECASE | re.DOTALL,
    )
    fragment = re.sub(
        r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>",
        "",
        fragment,
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in re.finditer(
        r"\b(?:src|poster)\s*=\s*[\"']([^\"']+)[\"']",
        fragment,
        flags=re.IGNORECASE,
    ):
        target = match.group(1).strip()
        parsed = urlsplit(target)
        if target.startswith(("#", "//")) or parsed.scheme:
            continue
        fail(
            "计算结果包含未嵌入的资源，请使用 embed-resources: true 重新渲染："
            f"{result_path.relative_to(PROJECT_ROOT)} -> {target}"
        )

    def shift_heading(match: re.Match[str]) -> str:
        level = min(6, int(match.group(2)) + 2)
        return f"{match.group(1)}h{level}{match.group(3)}"

    fragment = re.sub(
        r"(<\/?)(?:h)([1-6])(\b[^>]*>)",
        shift_heading,
        fragment,
        flags=re.IGNORECASE,
    )
    return prefix_computation_identifiers(fragment.strip(), prefix)


def inject_computation_results(
    pages: list[QuartoPage],
    orders: dict[str, list[ComputationGroup]],
) -> dict[Path, str]:
    if not orders:
        return {}
    pages_by_title: dict[str, Path] = {}
    for page in pages:
        if not page.blocks or page.blocks[0].get("t") != "Header":
            continue
        title = ast_plain_text(page.blocks[0]["c"][2]).strip()
        if title:
            pages_by_title[title] = QUARTO_PROJECT_DIR / page.source_path
            # Quarto adds the printed chapter number to chapter headers, while
            # computations.order is intentionally written with the plain title.
            normalized_title = re.sub(r"^第\s*\d+\s*章\s*", "", title).strip()
            pages_by_title.setdefault(
                normalized_title,
                QUARTO_PROJECT_DIR / page.source_path,
            )

    appendices: dict[Path, str] = {}
    for chapter_title, groups in orders.items():
        qmd_path = pages_by_title.get(chapter_title)
        if qmd_path is None or not qmd_path.is_file():
            fail(f"找不到数值计算结果对应的网页章节：{chapter_title}")

        articles: list[str] = []
        for group_index, group in enumerate(groups, start=1):
            results: list[str] = []
            for result_index, result_path in enumerate(
                group.result_paths,
                start=1,
            ):
                language = result_path.parent.name.lower()
                label = {
                    "python": "Python · Jupyter",
                    "r": "R · Quarto",
                }.get(language, result_path.parent.name)
                prefix = f"computation-{group_index:02d}-{result_index:02d}-"
                fragment = extract_computation_fragment(result_path, prefix)
                results.append(
                    '<section class="computation-result">'
                    '<div class="computation-result-label">'
                    f"{html.escape(label)}</div>"
                    '<div class="computation-result-body">'
                    f"{fragment}</div></section>"
                )
            articles.append(
                f'<article class="computation-case" id="computation-case-{group_index:02d}">'
                '<div class="computation-case-index">'
                f'<span>实验</span><strong>{group_index:02d}</strong></div>'
                f'<h3>{html.escape(group.title)}</h3>'
                + "".join(results)
                + "</article>"
            )

        appendix = (
            '<section class="computation-appendix" id="computed-results">'
            '<header class="computation-appendix-header">'
            '<p>COMPUTATIONAL NOTES</p><h2>计算实验</h2>'
            "</header>"
            + "".join(articles)
            + "</section>"
        )
        appendices[qmd_path] = appendix
    log(f"已插入 {sum(len(groups) for groups in orders.values())} 个计算实验")
    return appendices


def append_computation_html(
    appendices: dict[Path, str],
    rendered_site: Path,
) -> None:
    """Append rendered computation HTML after Quarto has preserved its math."""
    for qmd_path, appendix in appendices.items():
        relative_html = qmd_path.relative_to(QUARTO_PROJECT_DIR).with_suffix(".html")
        html_path = rendered_site / relative_html
        if not html_path.is_file():
            fail(f"找不到数值实验对应的已渲染网页：{relative_html}")
        markup = html_path.read_text(encoding="utf-8")
        closing_main = re.search(r"</main>", markup, flags=re.IGNORECASE)
        if closing_main is None:
            fail(f"网页缺少 main 容器，无法插入数值实验：{relative_html}")
        position = closing_main.start()
        markup = markup[:position] + appendix + "\n" + markup[position:]
        markup = append_computation_toc(markup, appendix)
        html_path.write_text(markup, encoding="utf-8")


def append_computation_toc(markup: str, appendix: str) -> str:
    """Add a compact, hierarchical computation entry to Quarto's page TOC."""
    toc_start = markup.find('<nav id="TOC"')
    if toc_start < 0:
        return markup
    toc_end = markup.find("</nav>", toc_start)
    if toc_end < 0:
        return markup
    first_ul = markup.find("<ul", toc_start, toc_end)
    last_ul = markup.rfind("</ul>", first_ul, toc_end)
    if first_ul < 0 or last_ul < 0:
        return markup

    cases = re.findall(
        r'<article\b[^>]*id="(computation-case-[^"]+)"[^>]*>.*?'
        r'<h3\b[^>]*>(.*?)</h3>',
        appendix,
        flags=re.IGNORECASE | re.DOTALL,
    )
    case_links = "".join(
        f'<li><a href="#{identifier}" class="nav-link" '
        f'data-scroll-target="#{identifier}">实验 {index:02d} · {title}</a></li>'
        for index, (identifier, title) in enumerate(cases, start=1)
    )
    toc_item = (
        '<li class="computation-toc-item">'
        '<a href="#computed-results" class="nav-link" '
        'data-scroll-target="#computed-results">计算实验</a>'
        f'<ul class="collapse">{case_links}</ul></li>'
    )
    return markup[:last_ul] + toc_item + markup[last_ul:]


def write_quarto_site(
    document: dict[str, Any],
    transformer: BookTransformer,
    output_dir: Path,
    computation_orders: dict[str, list[ComputationGroup]],
    site_metadata: dict[str, str],
    chapter_progress: dict[str, int | None],
    notation_catalog: dict[str, Any],
) -> None:
    if not QUARTO.exists():
        fail(
            "找不到 Quarto。可通过环境变量 QUARTO 指定可执行文件，"
            f"当前路径：{QUARTO}"
        )
    clean_generated_directory(QUARTO_PROJECT_DIR)
    QUARTO_PROJECT_DIR.mkdir(parents=True)

    sanitize_quarto_identifiers(document)
    copy_quarto_resources(document)
    pages = split_quarto_pages(document, transformer)
    add_reference_page(pages)
    expected_progress_keys = {
        page.source_path.stem
        for page in pages
        if page.part not in {None, "中英术语表"}
    }
    configured_progress_keys = set(chapter_progress)
    if expected_progress_keys != configured_progress_keys:
        missing = sorted(expected_progress_keys - configured_progress_keys)
        unknown = sorted(configured_progress_keys - expected_progress_keys)
        details: list[str] = []
        if missing:
            details.append("缺少：" + "、".join(missing))
        if unknown:
            details.append("未知：" + "、".join(unknown))
        fail("chapter-progress.json 必须与正文 19 章完全一致（" + "；".join(details) + "）")
    labels_to_pages: dict[str, Path] = {}
    for page in pages:
        identifiers: set[str] = set()
        collect_identifiers(page.blocks, identifiers)
        for identifier in identifiers:
            labels_to_pages[identifier] = page.source_path
    for page in pages:
        page.blocks = rewrite_quarto_targets(
            page.blocks,
            page.source_path,
            labels_to_pages,
        )
        write_qmd_page(page, document, chapter_progress)

    computation_appendices = inject_computation_results(pages, computation_orders)

    write_quarto_config(
        document,
        pages,
        transformer,
        site_metadata,
        chapter_progress,
        notation_catalog,
    )
    quarto_home = BUILD_DIR / "quarto-home"
    quarto_cache = BUILD_DIR / "quarto-cache"
    deno_cache = BUILD_DIR / "deno-cache"
    for directory in (quarto_home, quarto_cache, deno_cache):
        directory.mkdir(parents=True, exist_ok=True)
    run(
        [str(QUARTO), "render"],
        cwd=QUARTO_PROJECT_DIR,
        environment={
            "HOME": str(quarto_home),
            "QUARTO_CACHE_DIR": str(quarto_cache),
            "DENO_DIR": str(deno_cache),
        },
    )

    append_computation_html(computation_appendices, QUARTO_PROJECT_DIR / "_site")

    rendered_index = QUARTO_PROJECT_DIR / "_site" / "index.html"
    index_html = rendered_index.read_text(encoding="utf-8")
    index_html = re.sub(
        r'<nav class="page-navigation">.*?</nav>',
        "",
        index_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # The Home page is its own layout.  Quarto automatically adds its
    # page-column helpers to raw sections, which makes the hero inherit the
    # book's narrow reading grid and shifts its contents unexpectedly.
    index_html = index_html.replace(
        '<div class="textbook-home page-columns page-full">',
        '<div class="textbook-home">',
    ).replace(
        '<section class="home-intro page-columns page-full"',
        '<section class="home-intro"',
    )
    index_html = index_html.replace(
        '<div class="quarto-title-meta-heading">修改于</div>',
        '<div class="quarto-title-meta-heading">编译于</div>',
    ).replace(
        '<div class="quarto-title-meta-heading">Modified</div>',
        '<div class="quarto-title-meta-heading">编译于</div>',
    )
    rendered_index.write_text(index_html, encoding="utf-8")

    clean_generated_directory(output_dir)
    shutil.copytree(QUARTO_PROJECT_DIR / "_site", output_dir)
    postprocess_reference_pages(output_dir)
    postprocess_site_markup(output_dir, site_metadata)
    cache_bust_favicon(output_dir)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")


def write_site(
    document: dict[str, Any],
    output_dir: Path,
    split_level: int,
) -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    ast_path = BUILD_DIR / "book.json"
    ast_path.write_text(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    clean_generated_directory(output_dir)
    relative_output = output_dir.relative_to(HTML_DIR)
    command = [
        "pandoc",
        str(ast_path.relative_to(HTML_DIR)),
        "--from=json",
        "--to=chunkedhtml",
        "--standalone",
        "--toc",
        "--toc-depth=3",
        f"--split-level={split_level}",
        "--chunk-template=%n-%i.html",
        "--mathjax",
        "--citeproc",
        f"--bibliography={PROJECT_ROOT / 'ref.bib'}",
        "--syntax-highlighting=pygments",
        "--variable=lang:zh-CN",
        "--variable=toc:true",
        "--css=style.css",
        f"--resource-path={PROJECT_ROOT}{os.pathsep}{HTML_DIR}",
        "--output",
        str(relative_output),
    ]
    run(command, cwd=HTML_DIR)
    shutil.copy2(HTML_DIR / "style.css", output_dir / "style.css")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")


def remove_div_by_id(markup: str, identifier: str) -> str:
    start_match = re.search(
        rf'<div\b(?=[^>]*\bid=["\']{re.escape(identifier)}["\'])[^>]*>',
        markup,
        flags=re.IGNORECASE,
    )
    if not start_match:
        return markup

    depth = 0
    div_tags = re.finditer(r"</?div\b[^>]*>", markup[start_match.start() :], re.I)
    for tag_match in div_tags:
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


def postprocess_reference_pages(output_dir: Path) -> None:
    references_page = output_dir / "references.html"
    if not references_page.exists():
        return

    references_relative_to_site = references_page.relative_to(output_dir).as_posix()
    for path in sorted(output_dir.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        if path.resolve() == references_page.resolve():
            updated = text
        else:
            current_directory = path.parent.relative_to(output_dir).as_posix()
            if current_directory == ".":
                current_directory = ""
            references_target = posixpath.relpath(
                references_relative_to_site,
                start=current_directory or ".",
            )
            updated = re.sub(
                r'href="#(ref-[^"]+)"',
                rf'href="{references_target}#\1"',
                text,
            )
            updated = remove_div_by_id(updated, "refs")
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def postprocess_site_markup(
    output_dir: Path, site_metadata: dict[str, str]
) -> None:
    """Add project metadata and stable, low-risk image loading hints."""
    repository_meta = (
        '<meta name="textbook-repository" content="'
        + html.escape(site_metadata["repository"], quote=True)
        + '">\n'
    )

    def embedded_png_dimensions(tag: str) -> tuple[int, int] | None:
        """Read a data-URI PNG size without decoding the whole image."""
        source_match = re.search(
            r"\bsrc\s*=\s*([\"'])data:image/png;base64,([^\"']+)\1",
            tag,
            flags=re.IGNORECASE,
        )
        if source_match is None:
            return None
        encoded = re.sub(r"\s+", "", source_match.group(2))
        try:
            # A PNG stores its width and height in bytes 16--23.  The first
            # 32 Base64 characters decode to the 24 bytes needed here.
            header = base64.b64decode(encoded[:32], validate=True)
        except (ValueError, binascii.Error):
            return None
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        if width <= 0 or height <= 0:
            return None
        return width, height

    def optimize_image(match: re.Match[str]) -> str:
        tag = match.group(0)
        closing = "/>" if tag.endswith("/>") else ">"
        core = tag[: -len(closing)].rstrip()
        is_embedded_image = bool(
            re.search(
                r"\bsrc\s*=\s*([\"'])data:image/",
                tag,
                flags=re.IGNORECASE,
            )
        )
        dimensions = embedded_png_dimensions(tag)
        if dimensions is not None:
            width, height = dimensions
            if not re.search(r"\bwidth\s*=", tag, flags=re.IGNORECASE):
                core += f' width="{width}"'
            if not re.search(r"\bheight\s*=", tag, flags=re.IGNORECASE):
                core += f' height="{height}"'
        if not re.search(r"\bloading\s*=", tag, flags=re.IGNORECASE):
            # Embedded computation figures are already part of the HTML file:
            # lazy loading saves no transfer and leaves their layout unresolved
            # while the browser positions chapter anchors.  Eagerly initialize
            # them; keep ordinary file-backed figures lazy.
            loading = "eager" if is_embedded_image else "lazy"
            core += f' loading="{loading}"'
        if not re.search(r"\bdecoding\s*=", tag, flags=re.IGNORECASE):
            core += ' decoding="async"'
        return core + closing

    for path in sorted(output_dir.rglob("*.html")):
        markup = path.read_text(encoding="utf-8")
        if 'name="textbook-repository"' not in markup:
            markup = markup.replace("</head>", repository_meta + "</head>", 1)
        markup = re.sub(
            r"<img\b[^>]*>",
            optimize_image,
            markup,
            flags=re.IGNORECASE,
        )
        path.write_text(markup, encoding="utf-8")


def cache_bust_favicon(output_dir: Path) -> None:
    """Version favicon URLs so browsers do not retain an obsolete icon."""
    favicon = output_dir / "favicon.svg"
    if not favicon.is_file():
        return

    version = hashlib.sha256(favicon.read_bytes()).hexdigest()[:12]
    icon_link = re.compile(
        r'(<link\b(?=[^>]*\brel=["\']icon["\'])[^>]*\bhref=["\'])'
        r'([^"\']*favicon\.svg)(?:\?[^"\']*)?(["\'])',
        flags=re.IGNORECASE,
    )
    for path in sorted(output_dir.rglob("*.html")):
        markup = path.read_text(encoding="utf-8")
        updated = icon_link.sub(rf"\1\2?v={version}\3", markup)
        if updated != markup:
            path.write_text(updated, encoding="utf-8")


def localize_navigation(output_dir: Path) -> None:
    replacements = {
        '<span class="navlink-label">Next:</span>': (
            '<span class="navlink-label">下一页：</span>'
        ),
        '<span class="navlink-label">Previous:</span>': (
            '<span class="navlink-label">上一页：</span>'
        ),
        '<span class="navlink-label">Up:</span>': (
            '<span class="navlink-label">上级：</span>'
        ),
        '<span class="navlink-label">Top:</span>': (
            '<span class="navlink-label">首页：</span>'
        ),
    }
    for path in output_dir.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        for source, replacement in replacements.items():
            text = text.replace(source, replacement)
        path.write_text(text, encoding="utf-8")


def validate_site(output_dir: Path) -> dict[str, Any]:
    pages: dict[Path, LinkCollector] = {}
    for path in sorted(output_dir.rglob("*.html")):
        markup = path.read_text(encoding="utf-8")
        collector = LinkCollector()
        collector.feed(markup)
        pages[path.resolve()] = collector

    broken_links: list[dict[str, str]] = []
    duplicate_ids: dict[str, list[str]] = {}
    for page, collector in pages.items():
        if collector.duplicate_identifiers:
            duplicate_ids[str(page.relative_to(PROJECT_ROOT))] = sorted(
                collector.duplicate_identifiers
            )
        for href in collector.links:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc:
                continue
            if href.startswith("#fnref"):
                continue
            target_path = (
                (page.parent / unquote(parsed.path)).resolve()
                if parsed.path
                else page
            )
            if target_path.is_dir():
                target_path = target_path / "index.html"
            target_page = pages.get(target_path)
            if target_page is None:
                if target_path.exists():
                    continue
                broken_links.append(
                    {
                        "page": str(page.relative_to(PROJECT_ROOT)),
                        "href": href,
                        "reason": "目标文件不存在",
                    }
                )
                continue
            fragment = unquote(parsed.fragment)
            if fragment and fragment not in target_page.identifiers:
                broken_links.append(
                    {
                        "page": str(page.relative_to(PROJECT_ROOT)),
                        "href": href,
                        "reason": "目标锚点不存在",
                    }
                )
    return {
        "html_pages": len(pages),
        "broken_links": broken_links,
        "duplicate_ids": duplicate_ids,
    }


def write_build_report(
    output_dir: Path,
    validation: dict[str, Any],
    transformer: BookTransformer,
    glossary_warnings: list[str],
) -> None:
    report = {
        **validation,
        "used_terms": len(transformer.used_terms),
        "glossary_entries": transformer.glossary_entry_count,
        "glossary_keys": transformer.glossary_key_count,
        "missing_terms": sorted(transformer.missing_terms),
        "unresolved_references": sorted(transformer.unresolved_references),
        "glossary_warnings": glossary_warnings,
    }
    (output_dir / "build-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def serve_site(output_dir: Path, port: int) -> None:
    os.chdir(output_dir)
    server = ThreadingHTTPServer(("127.0.0.1", port), SimpleHTTPRequestHandler)
    log(f"预览地址：http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        log("预览服务器已停止")
    finally:
        server.server_close()


def build(arguments: argparse.Namespace) -> int:
    ensure_tool("pandoc")
    if not MAIN_TEX.exists() or not SETTINGS_TEX.exists():
        fail("必须从 textbook 项目中运行，且项目根目录需要 main.tex/settings.tex")

    output_dir = (HTML_DIR / arguments.output).resolve()
    if not is_inside(output_dir, HTML_DIR):
        fail("输出目录必须位于 html/ 内")

    computation_orders = load_computation_orders()
    site_metadata = load_site_metadata()
    chapter_progress = load_chapter_progress()
    notation_catalog = load_notation_catalog()

    log("读取术语和定理配置")
    (
        glossary,
        terms_by_directory,
        conflicting_term_keys,
        glossary_warnings,
        glossary_catalog,
    ) = load_glossary()
    theorem_specs = parse_theorem_specs()
    for warning in glossary_warnings:
        print(f"[web] 警告：{warning}", file=sys.stderr)
    log(
        f"发现 {len(glossary_catalog)} 条 NewTerm、"
        f"{len(glossary)} 个唯一术语键、"
        f"{len(theorem_specs)} 类定理环境"
    )

    stage_sources(
        theorem_specs,
        glossary,
        terms_by_directory,
        conflicting_term_keys,
    )
    log("Pandoc 正在解析完整 LaTeX 文档")
    document = parse_latex_to_ast()

    transformer = BookTransformer(
        theorem_specs,
        glossary,
        glossary_catalog,
    )
    document = transformer.transform(document)

    log("使用 Quarto Book 生成多页面 HTML")
    write_quarto_site(
        document,
        transformer,
        output_dir,
        computation_orders,
        site_metadata,
        chapter_progress,
        notation_catalog,
    )
    validation = validate_site(output_dir)
    write_build_report(
        output_dir,
        validation,
        transformer,
        glossary_warnings,
    )

    if transformer.missing_terms:
        print(
            "[web] 未找到定义的术语："
            + ", ".join(sorted(transformer.missing_terms)),
            file=sys.stderr,
        )
    if transformer.unresolved_references:
        print(
            "[web] 未解析的交叉引用："
            + ", ".join(sorted(transformer.unresolved_references)),
            file=sys.stderr,
        )

    log(
        f"完成：{output_dir.relative_to(PROJECT_ROOT)} "
        f"（{validation['html_pages']} 个页面，"
        f"使用术语 {len(transformer.used_terms)} 个，"
        f"术语表 {transformer.glossary_entry_count} 条，"
        f"失效链接 {len(validation['broken_links'])} 个）"
    )
    if arguments.strict and (
        transformer.missing_terms or transformer.unresolved_references
    ):
        return 2
    if arguments.serve:
        serve_site(output_dir, arguments.port)
    return 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 main.tex 转换成保留章节与数学环境的多页面 HTML"
    )
    parser.add_argument(
        "--output",
        default="site",
        help="html/ 内的输出目录，默认 site",
    )
    parser.add_argument(
        "--split",
        choices=("part", "chapter", "section"),
        default="chapter",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="存在未定义术语或未解析引用时返回失败",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="构建完成后启动本地预览服务器",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="本地预览端口，默认 8000",
    )
    return parser.parse_args()


def main() -> int:
    try:
        return build(parse_arguments())
    except RuntimeError as error:
        print(f"[web] 错误：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
