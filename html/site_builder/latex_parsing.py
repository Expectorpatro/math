"""Balanced-delimiter helpers shared by LaTeX preprocessors."""

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
