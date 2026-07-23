"""Glossary-page construction for the Pandoc book transformer."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .errors import BuildError
from .pandoc_ast import make_attr, scoped_term_key, space_inline, str_inline
from .pandoc_tables import latex_to_html_fragment, latex_to_plain


def fail(message: str) -> None:
    raise BuildError(message)


class GlossaryAppenderMixin:
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
                    [str_inline("中英术语表")],
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
                    if self.project_root is None:
                        fail("生成重复术语锚点需要明确的项目根目录")
                    source_directory = (self.project_root / term.source).parent
                    scoped_key = scoped_term_key(
                        source_directory,
                        term.key,
                        self.project_root,
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
