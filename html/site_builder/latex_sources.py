"""LaTeX source discovery, preprocessing, and isolated staging."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import Any, Iterable

from .commands import CommandRunner
from .config import BuildConfig, BuildPaths
from .constants import (
    ALGORITHM_COMMAND_PREFIX,
    ALGORITHM_TITLE_END_PREFIX,
    ALGORITHM_TITLE_START_PREFIX,
    DENSITY_PLOT_MARKER_PREFIX,
    DENSITY_PLOT_NAMES,
    TABLE_MARKER_PREFIX,
    TITLE_END_PREFIX,
    TITLE_MARKER_PREFIX,
    TITLE_START_PREFIX,
    TODO_END_PREFIX,
    TODO_START_PREFIX,
)
from .errors import BuildError
from .filesystem import prepare_empty_directory
from .images import TikzRenderer
from .models import LatexTable, LatexTableCell, LatexTableRow, Term, TheoremSpec
from .pandoc_transform import scoped_term_key


def fail(message: str) -> None:
    raise BuildError(message)


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def clean_generated_directory(
    path: Path,
    *,
    managed: tuple[Path, ...],
) -> None:
    prepare_empty_directory(
        path,
        managed=managed,
    )


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
    text: str,
    marker_counter: list[int],
    tables: dict[str, LatexTable],
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
        tables[marker] = table
        return rf"\par\textbf{{{TABLE_MARKER_PREFIX}{marker}}}\par"

    return pattern.sub(replacement, text)


def parse_new_terms(
    text: str,
    source: Path,
    *,
    project_root: Path,
) -> list[Term]:
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
                    source=str(source.relative_to(project_root)),
                )
            )
        cursor = position
    return terms


def load_glossary(paths: BuildPaths) -> tuple[
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
    for path in sorted(paths.project_root.rglob("english.tex")):
        if is_inside(path, paths.html_dir):
            continue
        text = strip_tex_comments(path.read_text(encoding="utf-8"))
        for term in parse_new_terms(
            text,
            path,
            project_root=paths.project_root,
        ):
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


def parse_theorem_specs(paths: BuildPaths) -> dict[str, TheoremSpec]:
    text = strip_tex_comments(paths.settings_tex.read_text(encoding="utf-8"))
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


def patch_scoped_glossary_terms(
    text: str,
    source: Path,
    glossary: dict[str, Term],
    terms_by_directory: dict[Path, dict[str, Term]],
    conflicting_keys: set[str],
    *,
    project_root: Path,
) -> str:
    if not conflicting_keys:
        return text

    def replacement(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in conflicting_keys:
            return match.group(0)
        directory = source.parent
        while is_inside(directory, project_root):
            local_term = terms_by_directory.get(directory, {}).get(key)
            if local_term is not None:
                synthetic_key = scoped_term_key(directory, key, project_root)
                glossary[synthetic_key] = Term(
                    key=synthetic_key,
                    english=local_term.english,
                    chinese=local_term.chinese,
                    source=local_term.source,
                )
                return rf"\gls{{{synthetic_key}}}"
            if directory == project_root:
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
    *,
    renderer: TikzRenderer,
) -> Path:
    """Render one generated TikZ picture through the shared quality policy."""

    # The index remains in the compatibility signature, but content-addressed
    # caching no longer depends on source order. Inserting a preceding figure
    # therefore does not invalidate every subsequent cached asset.
    del picture_index
    return renderer.render(tikz_source, source)


def patch_density_plots(
    text: str,
    source: Path,
    rendered_counter: list[int],
    *,
    project_root: Path,
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
            relative = source.relative_to(project_root)
            fail(f"未知的密度图类型 {name!r}：{relative}")
        rendered_counter[0] += 1
        return f"\n\n{DENSITY_PLOT_MARKER_PREFIX}{name}\n\n"

    return pattern.sub(replacement, text)


def patch_tikz_pictures(
    text: str,
    source: Path,
    rendered_counter: list[int],
    *,
    renderer: TikzRenderer,
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
            renderer=renderer,
        )
        return (
            match.group("indent")
            + rf"\includegraphics[width=0.92\linewidth]"
            + rf"{{{target.as_posix()}}}"
        )

    patched = pattern.sub(replacement, text)
    # Pandoc recognizes a direct \includegraphics command, but drops an image
    # whose only purpose is hidden inside a LaTeX \makebox.  Unwrap only the
    # makeboxes that contain exactly one generated TikZ image.
    tikz_makebox_pattern = re.compile(
        r"\\makebox\s*(?:\[[^\]\r\n]*\]\s*){0,2}"
        r"\{\s*%?\s*"
        r"(?P<image>\\includegraphics\s*"
        r"(?:\[[^\]\r\n]*\]\s*)?"
        r"\{_tikz/[^{}\r\n]+\})"
        r"\s*%?\s*\}",
        flags=re.DOTALL,
    )
    return tikz_makebox_pattern.sub(
        lambda match: match.group("image"),
        patched,
    )


def patch_main_for_full_book(text: str, *, project_root: Path) -> str:
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
            target = project_root / f"{match.group('value')}.tex"
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
    *,
    config: BuildConfig,
    runner: CommandRunner,
) -> dict[str, LatexTable]:
    paths = config.paths
    managed_directories = (
        paths.staged_source_dir,
        paths.tikz_work_dir,
    )
    clean_generated_directory(
        paths.staged_source_dir,
        managed=managed_directories,
    )
    clean_generated_directory(
        paths.tikz_work_dir,
        managed=managed_directories,
    )
    tikz_renderer = TikzRenderer(config, runner)
    marker_counter = [0]
    algorithm_marker_counter = [0]
    density_plot_counter = [0]
    tikz_counter = [0]
    todo_marker_counter = [0]
    table_marker_counter = [0]
    staged_tables: dict[str, LatexTable] = {}
    copied = 0
    copied_code_files: set[Path] = set()
    for source in sorted(paths.project_root.rglob("*.tex")):
        if is_inside(source, paths.html_dir):
            continue
        relative = source.relative_to(paths.project_root)
        destination = paths.staged_source_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8")
        if source == paths.main_tex:
            text = patch_main_for_full_book(
                text,
                project_root=paths.project_root,
            )
        text = patch_scoped_glossary_terms(
            text,
            source,
            glossary,
            terms_by_directory,
            conflicting_keys,
            project_root=paths.project_root,
        )
        if source != paths.settings_tex:
            text = patch_todo_macros(text, todo_marker_counter)
        text = patch_latex_tables(text, table_marker_counter, staged_tables)
        text = patch_custom_math_environments(text)
        text = patch_algorithm_environments(
            text, algorithm_marker_counter
        )
        text = patch_density_plots(
            text,
            source,
            density_plot_counter,
            project_root=paths.project_root,
        )
        text = patch_tikz_pictures(
            text,
            source,
            tikz_counter,
            renderer=tikz_renderer,
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
                paths.project_root / requested,
                source.parent / requested,
            ]
            code_source = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.is_file()
                    and is_inside(candidate, paths.project_root)
                ),
                None,
            )
            if code_source is None:
                continue
            code_relative = code_source.relative_to(paths.project_root)
            code_destination = paths.staged_source_dir / code_relative
            code_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(code_source, code_destination)
            copied_code_files.add(code_relative)
        copied += 1
    runner.log(
        f"已暂存 {copied} 个 TeX 文件、"
        f"{len(copied_code_files)} 个代码文件，"
        f"标记 {marker_counter[0]} 个环境标题、"
        f"{algorithm_marker_counter[0]} 个算法，"
        f"{density_plot_counter[0]} 幅交互密度图、"
        f"转换 {tikz_counter[0]} 幅 TikZ 图片、"
        f"转换 {table_marker_counter[0]} 张 LaTeX 表格、"
        f"保留 {todo_marker_counter[0]} 条项目批注"
    )
    return staged_tables
