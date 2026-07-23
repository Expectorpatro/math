"""Conversion of algorithmicx environments for Pandoc and MathJax."""

from __future__ import annotations

import re
from typing import Any

from .constants import (
    ALGORITHM_COMMAND_PREFIX,
    ALGORITHM_TITLE_END_PREFIX,
    ALGORITHM_TITLE_START_PREFIX,
)
from .latex_parsing import read_balanced, skip_space

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
