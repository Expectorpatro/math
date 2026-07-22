"""Structured Quarto project configuration and navigation output."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .config import BuildConfig
from .markup import YamlEmitter
from .models import QuartoPage


def build_chapter_navigation(pages: list[QuartoPage]) -> list[Any]:
    """Build Quarto's chapter tree while preserving the existing ordering."""

    chapters: list[Any] = ["index.qmd"]
    current_part: str | None = None
    current_group: dict[str, Any] | None = None
    for page in pages:
        if page.part is None or page.part == "中英术语表":
            current_part = None
            current_group = None
            chapters.append(page.source_path.as_posix())
            continue
        if page.part != current_part:
            current_part = page.part
            current_group = {"part": current_part, "chapters": []}
            chapters.append(current_group)
        assert current_group is not None
        current_group["chapters"].append(page.source_path.as_posix())
    chapters.append(
        {
            "part": "项目",
            "chapters": ["project-status.qmd", "notation.qmd"],
        }
    )
    return chapters


class QuartoProjectWriter:
    """Write the small generated files that define a Quarto book project."""

    def __init__(self, config: BuildConfig) -> None:
        self.config = config
        self.emitter = YamlEmitter()

    def write_config(
        self,
        *,
        pages: list[QuartoPage],
        title: str,
        author: str,
        email: str,
        publication_date: str,
        description: str,
        site_url: str,
        repository_url: str,
    ) -> Path:
        """Render ``_quarto.yml`` from typed inputs rather than line fragments."""

        book: dict[str, Any] = {
            "title": title,
            "description": description,
            "site-url": site_url,
            "repo-url": repository_url,
            "favicon": "favicon.svg",
        }
        if author:
            book["author"] = (
                [{"name": author, "email": email}]
                if email
                else author
            )
        if publication_date:
            book["date"] = publication_date
        book.update(
            {
                "search": True,
                "page-navigation": True,
                "sidebar": {"style": "docked", "collapse-level": 2},
                "chapters": build_chapter_navigation(pages),
            }
        )

        bibliography = os.path.relpath(
            self.config.paths.project_root / "ref.bib",
            self.config.paths.quarto_project_dir,
        ).replace(os.sep, "/")
        html_format: dict[str, Any] = {
            "theme": {"light": "cosmo", "dark": "darkly"},
            "include-in-header": self.config.assets.header_template,
            "css": [self.config.assets.style_bundle, "sidebar.css"],
            "toc": True,
            "toc-title": "本页目录",
            "toc-depth": self.config.render.toc_depth,
            "number-sections": False,
            "code-copy": True,
            "code-overflow": "wrap",
            "smooth-scroll": True,
            "link-external-newwindow": True,
            "open-graph": True,
            "twitter-card": True,
            "html-math-method": "mathjax",
            "grid": {
                "sidebar-width": f"{self.config.render.sidebar_width_px}px",
                "body-width": f"{self.config.render.body_width_px}px",
                "margin-width": f"{self.config.render.margin_width_px}px",
                "gutter-width": f"{self.config.render.gutter_rem:g}rem",
            },
        }
        project = {
            "project": {
                "type": "book",
                "output-dir": "_site",
                "resources": list(self.config.assets.quarto_resources),
            },
            "lang": self.config.render.language,
            "date-format": "long",
            "bibliography": bibliography,
            "csl": "textbook.csl",
            "book": book,
            "format": {"html": html_format},
        }
        destination = self.config.paths.quarto_project_dir / "_quarto.yml"
        destination.write_text(self.emitter.dumps(project), encoding="utf-8")
        return destination

    def write_sidebar_rules(self, pages: list[QuartoPage]) -> Path:
        """Hide auxiliary glossary pages without removing searchability."""

        hidden_pages = [
            page.source_path.with_suffix(".html").name
            for page in pages
            if not page.sidebar_visible
        ]
        rules = [
            "/* Generated: glossary letter pages stay searchable",
            "   without occupying the book sidebar. */",
        ]
        rules.extend(
            "#quarto-sidebar li.sidebar-item:has("
            "> .sidebar-item-container > "
            f'a.sidebar-link[href$="{filename}"]) {{ display: none; }}'
            for filename in hidden_pages
        )
        destination = self.config.paths.quarto_project_dir / "sidebar.css"
        destination.write_text("\n".join(rules) + "\n", encoding="utf-8")
        return destination


__all__ = ["QuartoProjectWriter", "build_chapter_navigation"]
