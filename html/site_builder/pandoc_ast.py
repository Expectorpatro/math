"""Small, reusable Pandoc AST constructors and marker rewrites."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from .constants import (
    REMOVE_AST_NODE,
    TITLE_END_PREFIX,
    TITLE_MARKER_PREFIX,
    TITLE_START_PREFIX,
    TODO_COMMANDS,
    TODO_END_PREFIX,
    TODO_START_PREFIX,
)


def scoped_term_key(directory: Path, key: str, project_root: Path) -> str:
    relative = directory.relative_to(project_root).as_posix()
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


def str_inline(value: str) -> dict[str, Any]:
    return {"t": "Str", "c": value}


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


def remove_labels_from_inlines(value: Any, labels: list[str]) -> Any:
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
    return remove_labels_from_inlines(blocks, labels), labels


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
            value["c"] = [
                str_inline("（"),
                *trim_inline_spaces(inlines[1:-1]),
                str_inline("）"),
            ]
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
