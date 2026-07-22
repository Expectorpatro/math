"""Shared domain models for the textbook HTML build."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class TheoremSpec:
    """Numbering and display metadata for one theorem environment."""

    environment: str
    printed_name: str
    counter: str
    parent: str | None
    reference_name: str


@dataclass(frozen=True, slots=True)
class Term:
    """One bilingual glossary entry discovered in a LaTeX source."""

    key: str
    english: str
    chinese: str
    source: str


@dataclass(slots=True)
class QuartoPage:
    """Pandoc blocks and navigation metadata for one generated page."""

    source_path: Path
    blocks: list[dict[str, Any]]
    part: str | None
    sidebar_visible: bool = True


@dataclass(frozen=True, slots=True)
class ComputationGroup:
    """Ordered rendered computations appended to one chapter."""

    title: str
    result_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class LatexTableCell:
    content: str
    colspan: int = 1
    alignment: str | None = None
    diagonal: tuple[str, str] | None = None


@dataclass(frozen=True, slots=True)
class LatexTableRow:
    cells: tuple[LatexTableCell, ...]
    rule_above: bool = False
    rule_below: bool = False


@dataclass(frozen=True, slots=True)
class LatexTable:
    caption: str
    alignments: tuple[str, ...]
    vertical_rules: frozenset[int]
    rows: tuple[LatexTableRow, ...]


__all__ = [
    "ComputationGroup",
    "LatexTable",
    "LatexTableCell",
    "LatexTableRow",
    "QuartoPage",
    "Term",
    "TheoremSpec",
]
