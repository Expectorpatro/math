#!/usr/bin/env python3
"""Build the LaTeX textbook as a multi-page HTML site.

The LaTeX sources remain the single source of truth.  This script stages copies
of the .tex files, lets Pandoc parse them into its JSON AST, applies the
project-specific theorem/glossary/reference rules, and asks Pandoc to write
chunked HTML.
"""

from __future__ import annotations

import argparse
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
from urllib.parse import unquote, urlsplit


HTML_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = HTML_DIR.parent
BUILD_DIR = HTML_DIR / ".build"
STAGED_SOURCE_DIR = BUILD_DIR / "source"
TIKZ_CACHE_DIR = BUILD_DIR / "tikz-cache"
TIKZ_WORK_DIR = BUILD_DIR / "tikz-work"
DEFAULT_OUTPUT_DIR = HTML_DIR / "site"
HOME_CONTENT = HTML_DIR / "home.md"
BIBLIOGRAPHY_STYLE = HTML_DIR / "textbook.csl"
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
    tikz_counter = [0]
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
        text = patch_custom_math_environments(text)
        text = patch_algorithm_environments(
            text, algorithm_marker_counter
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
        f"转换 {tikz_counter[0]} 幅 TikZ 图片"
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
        for inline in self.iter_math_nodes(block["c"]):
            if inline["c"][0].get("t") != "DisplayMath":
                continue
            source = inline["c"][1]
            labels = re.findall(r"\\label\s*\{([^{}]+)\}", source)
            before = self.equation
            self.increment_unlabelled_equations(source)
            standard_labels = [
                label for label in labels if not label.startswith("ineq:")
            ]
            if standard_labels and self.equation == before:
                self.equation += 1
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
                inline["c"][1] = source
        if not equation_labels:
            return block
        first_label = equation_labels[0][0]
        for additional_label, _ in reversed(equation_labels[1:]):
            block["c"].insert(
                0,
                {
                    "t": "Span",
                    "c": [make_attr(additional_label), []],
                },
            )
        return {
            "t": "Div",
            "c": [
                make_attr(first_label, classes=["equation-block"]),
                [block],
            ],
        }

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
                    classes.append("proof-block")
                    remove_pandoc_proof_prefix(block["c"][1])
                    block["c"][1] = self.process_blocks(block["c"][1])
                    result.append(block)
                    continue
                block["c"][1] = self.process_blocks(block["c"][1])
                result.append(block)
                continue
            if block_type in {"Para", "Plain"}:
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

    def transform_inlines(self, value: Any, *, rewrite_references: bool) -> Any:
        if isinstance(value, list):
            return [
                self.transform_inlines(item, rewrite_references=rewrite_references)
                for item in value
            ]
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
                    [str_inline("术语表总览")],
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
        shifted = shift_header_levels(
            current_blocks,
            1 - transformer.chapter_level,
        )
        pages.append(
            QuartoPage(
                source_path=Path("chapters") / f"page-{page_number:03d}.qmd",
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
    if page.source_path.name == "references.qmd":
        markdown = "---\nnocite: '@*'\n---\n\n" + markdown.lstrip()
    destination.write_text(markdown, encoding="utf-8")


def write_quarto_config(
    document: dict[str, Any],
    pages: list[QuartoPage],
) -> None:
    title = ast_plain_text(document["meta"].get("title", {})).strip()
    author = ast_plain_text(document["meta"].get("author", {})).strip()
    raw_date = ast_plain_text(document["meta"].get("date", {})).strip()
    date = quarto_date(raw_date)
    email = book_contact_email()
    title = title or "数学教材"

    index = [
        "---",
        f"title: {yaml_quote(title)}",
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
    index.extend(
        [
            "---",
            "",
            home_content,
        ]
    )
    if email:
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
        if page.part is None:
            current_part = None
            chapter_lines.append(f"    - {page.source_path.as_posix()}")
            continue
        if page.part != current_part:
            current_part = page.part
            chapter_lines.append(f"    - part: {yaml_quote(current_part)}")
            chapter_lines.append("      chapters:")
        chapter_lines.append(f"        - {page.source_path.as_posix()}")

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
        "",
        "lang: zh",
        "date-format: long",
        f"bibliography: {yaml_quote('../../../ref.bib')}",
        f"csl: {yaml_quote('textbook.csl')}",
        "",
        "book:",
        f"  title: {yaml_quote(title)}",
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
            "    css:",
            "      - style.css",
            "      - sidebar.css",
            "    toc: true",
            "    toc-depth: 4",
            "    number-sections: false",
            "    code-copy: true",
            "    code-overflow: wrap",
            "    smooth-scroll: true",
            "    link-external-newwindow: true",
            "    html-math-method: mathjax",
            "    grid:",
            "      sidebar-width: 320px",
            "      body-width: 1100px",
            "      margin-width: 210px",
            "      gutter-width: 1.15rem",
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
    shutil.copy2(
        HTML_DIR / "theme-toggle.html",
        QUARTO_PROJECT_DIR / "theme-toggle.html",
    )
    shutil.copy2(BIBLIOGRAPHY_STYLE, QUARTO_PROJECT_DIR / "textbook.csl")


def write_quarto_site(
    document: dict[str, Any],
    transformer: BookTransformer,
    output_dir: Path,
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
        write_qmd_page(page, document)

    write_quarto_config(document, pages)
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

    rendered_index = QUARTO_PROJECT_DIR / "_site" / "index.html"
    index_html = rendered_index.read_text(encoding="utf-8")
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
        "--toc-depth=5",
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
        collector = LinkCollector()
        collector.feed(path.read_text(encoding="utf-8"))
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
    write_quarto_site(document, transformer, output_dir)
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
