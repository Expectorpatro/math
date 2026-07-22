"""Write one planned Pandoc page as Quarto Markdown."""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import re
import textwrap
from typing import Any

from .models import QuartoPage
from .runtime import CONFIG, RUNNER

PROJECT_ROOT = CONFIG.paths.project_root
QUARTO_PROJECT_DIR = CONFIG.paths.quarto_project_dir


def run(
    command: list[str],
    *,
    cwd: Path,
    input_text: str | None = None,
) -> str:
    return RUNNER.run(command, cwd=cwd, input_text=input_text)


_FENCE = re.compile(r"^[ \t]*(?P<marker>`{3,}|~{3,})(?P<rest>.*)$")


def _outside_code_fences(
    source: str, transform: Callable[[str], str]
) -> str:
    """Apply *transform* only to Markdown that is not fenced code."""

    result: list[str] = []
    ordinary: list[str] = []
    active: tuple[str, int] | None = None

    def flush() -> None:
        if ordinary:
            result.append(transform("".join(ordinary)))
            ordinary.clear()

    for line in source.splitlines(keepends=True):
        match = _FENCE.match(line.rstrip("\r\n"))
        if active is None:
            if match:
                marker = match.group("marker")
                flush()
                result.append(line)
                active = (marker[0], len(marker))
            else:
                ordinary.append(line)
            continue
        result.append(line)
        if match:
            marker = match.group("marker")
            if (
                marker[0] == active[0]
                and len(marker) >= active[1]
                and not match.group("rest").strip()
            ):
                active = None
    flush()
    return "".join(result)


def collapse_excess_blank_lines(markdown: str) -> str:
    """Collapse prose whitespace while preserving code examples verbatim."""

    result: list[str] = []
    active_fence: tuple[str, int] | None = None
    previous_outside_line_was_blank = False
    for line in markdown.splitlines(keepends=True):
        fence = _FENCE.match(line.rstrip("\r\n"))
        if active_fence is not None:
            result.append(line)
            if fence:
                marker = fence.group("marker")
                if (
                    marker[0] == active_fence[0]
                    and len(marker) >= active_fence[1]
                    and not fence.group("rest").strip()
                ):
                    active_fence = None
                    previous_outside_line_was_blank = False
            continue
        if fence:
            marker = fence.group("marker")
            result.append(line)
            active_fence = (marker[0], len(marker))
            previous_outside_line_was_blank = False
            continue
        if not line.strip():
            if previous_outside_line_was_blank:
                continue
            previous_outside_line_was_blank = True
        else:
            previous_outside_line_was_blank = False
        result.append(line)
    return "".join(result)


def normalize_display_math(markdown: str, list_marker_pattern: str) -> str:
    """Normalize Pandoc display math without touching code examples."""

    def normalize_segment(segment: str) -> str:
        def list_continuation_indentation(line: str) -> str:
            marker = re.match(list_marker_pattern, line)
            if marker:
                return marker.group("indent") + " " * (
                    len(marker.group(0)) - len(marker.group("indent"))
                )
            return line[: len(line) - len(line.lstrip())]

        def format_display_math(match: re.Match[str]) -> str:
            source = textwrap.dedent(match.group("source")).strip()
            line_start = segment.rfind("\n", 0, match.start()) + 1
            line_before_match = segment[line_start : match.start()]
            line_prefix = line_before_match + match.group("leading")
            is_block = not line_prefix.strip()
            indentation = (
                "" if is_block else list_continuation_indentation(line_prefix)
            )

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
                math_block = indent_lines(source)
            else:
                math_block = (
                    f"{indentation}$$\n"
                    f"{indent_lines(source)}\n"
                    f"{indentation}$$"
                )
            if not is_block:
                return f"\n\n{math_block}\n\n{indentation}"
            return math_block

        return re.sub(
            r"(?P<leading>[ \t]*)\$\$(?P<source>.*?)\$\$(?P<trailing>[ \t]*)",
            format_display_math,
            segment,
            flags=re.DOTALL | re.MULTILINE,
        )

    return _outside_code_fences(markdown, normalize_segment)


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
            CONFIG.tools.pandoc,
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

    markdown = normalize_display_math(markdown, list_marker_pattern)

    lines = markdown.splitlines()
    list_levels: list[int] = []
    active_fence: tuple[str, int] | None = None
    for line_index, line in enumerate(lines):
        stripped = line.strip()
        fence = _FENCE.match(line)
        if active_fence is None and fence:
            marker = fence.group("marker")
            active_fence = (marker[0], len(marker))
            continue
        if active_fence is not None:
            if fence:
                marker = fence.group("marker")
                if (
                    marker[0] == active_fence[0]
                    and len(marker) >= active_fence[1]
                    and not fence.group("rest").strip()
                ):
                    active_fence = None
            continue
        if not stripped:
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

    markdown = collapse_excess_blank_lines(markdown)
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
