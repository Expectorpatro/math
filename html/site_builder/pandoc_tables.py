"""LaTeX table and short inline fragments rendered for Pandoc HTML."""

from __future__ import annotations

import html
import re

from .models import LatexTable

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
