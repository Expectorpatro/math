from __future__ import annotations

from pathlib import Path
import sys
import unittest


HTML_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HTML_DIR))

from site_builder.models import QuartoPage
from site_builder.pages import quarto_page_slug
from site_builder.site_content import (
    render_github_actions,
    render_progress_overview,
    render_recent_commits,
)


class StructuredSiteContentTests(unittest.TestCase):
    def test_unknown_page_slug_is_independent_of_page_position(self) -> None:
        first = quarto_page_slug("新的专题", "", 4)
        second = quarto_page_slug("新的专题", "", 19)

        self.assertEqual(first, second)
        self.assertRegex(first, r"^page-[0-9a-f]{10}$")

    def test_unknown_pages_with_same_title_use_distinct_identifiers(self) -> None:
        first = quarto_page_slug("同名专题", "chapter-one", 4)
        second = quarto_page_slug("同名专题", "chapter-two", 5)

        self.assertNotEqual(first, second)

    def test_recent_commits_escape_text_and_attributes(self) -> None:
        markup = render_recent_commits(
            {"github_url": "https://example.invalid/owner/book"},
            [
                {
                    "hash": 'abc123\" data-danger=\"1',
                    "short_hash": "abc<123",
                    "date": "2026-07-22",
                    "subject": "修正 <figure> & 标题",
                }
            ],
        )

        self.assertIn("abc&lt;123", markup)
        self.assertIn("修正 &lt;figure&gt; &amp; 标题", markup)
        self.assertIn("abc123&quot; data-danger=&quot;1", markup)
        self.assertNotIn('data-danger="1"', markup)

    def test_progress_overview_uses_generated_page_link(self) -> None:
        page = QuartoPage(
            source_path=Path("chapters/linear-space.qmd"),
            blocks=[
                {
                    "t": "Header",
                    "c": [1, ["", [], []], [{"t": "Str", "c": "线性空间"}]],
                }
            ],
            part="第一部分 线性代数",
        )

        markup = render_progress_overview([page], {"linear-space": 95})

        self.assertIn('href="chapters/linear-space.html"', markup)
        self.assertIn('style="--chapter-progress: 95%"', markup)
        self.assertIn("95%", markup)

    def test_github_actions_encode_issue_queries(self) -> None:
        markup = render_github_actions(
            {
                "github_url": "https://example.invalid/owner/book",
            }
        )

        self.assertIn("issues/new?", markup)
        self.assertIn("%E9%94%99%E8%AF%AF%E6%8A%A5%E5%91%8A", markup)
        self.assertNotIn("\n", markup)


if __name__ == "__main__":
    unittest.main()
