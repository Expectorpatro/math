"""LaTeX source discovery, preprocessing, and isolated staging."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import Iterable

from .commands import CommandRunner
from .config import BuildConfig, BuildPaths
from .constants import (
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
from .latex_algorithms import patch_algorithm_environments
from .models import LatexTable, LatexTableCell, LatexTableRow, Term, TheoremSpec
from .pandoc_ast import scoped_term_key
from .latex_parsing import read_balanced, skip_space


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
    def replacement(match: re.Match[str]) -> str:
        rendered_counter[0] += 1
        target = renderer.render(match.group("picture"), source)
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
