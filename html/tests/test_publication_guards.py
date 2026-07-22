from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
import unittest


HTML_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HTML_DIR))

from site_builder.errors import BuildError
from site_builder.freshness import (
    FINGERPRINT_FILENAME,
    is_site_source_path,
    source_fingerprint,
    verify_site_fingerprint,
    write_site_fingerprint,
)
from site_builder.validation import parse_css_references, validate_site


class ProjectTemporaryDirectory(tempfile.TemporaryDirectory[str]):
    """Keep test writes inside the project's ignored build directory."""

    def __init__(self) -> None:
        root = HTML_DIR / ".build" / "tests"
        root.mkdir(parents=True, exist_ok=True)
        super().__init__(dir=root)


class FinalSiteValidationTests(unittest.TestCase):
    def test_duplicate_resource_ids_are_publication_errors(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            (site / "index.html").write_text(
                '<link id="theme" href="style.css">'
                '<script id="theme" src="app.js"></script>',
                encoding="utf-8",
            )
            (site / "style.css").write_text("", encoding="utf-8")
            (site / "app.js").write_text("", encoding="utf-8")

            report = validate_site(site)

            self.assertTrue(report.has_errors)
            self.assertEqual(
                report.duplicate_resource_ids,
                {"index.html": ["theme"]},
            )

    def test_cross_kind_duplicate_id_is_not_missed(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            (site / "index.html").write_text(
                '<script id="shared"></script><main id="shared"></main>',
                encoding="utf-8",
            )

            report = validate_site(site)

            self.assertEqual(report.duplicate_ids, {"index.html": ["shared"]})
            self.assertTrue(report.has_errors)

    def test_checks_embedded_svg_media_and_css_references(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            (site / "index.html").write_text(
                "<style>.hero { background: url('missing-inline.png'); }</style>"
                '<embed src="missing-document.pdf">'
                '<track src="missing-captions.vtt">'
                '<svg><use href="#missing-symbol"></use></svg>',
                encoding="utf-8",
            )
            (site / "style.css").write_text(
                '@import "missing-theme.css"; '
                '.icon { background-image: url("missing-font.woff2"); }',
                encoding="utf-8",
            )

            report = validate_site(site)
            targets = {
                next(
                    value
                    for key, value in issue.items()
                    if key not in {"page", "reason"}
                )
                for issue in report.broken_resources
            }

            self.assertEqual(
                targets,
                {
                    "#missing-symbol",
                    "missing-captions.vtt",
                    "missing-document.pdf",
                    "missing-font.woff2",
                    "missing-inline.png",
                    "missing-theme.css",
                },
            )

    def test_css_reference_parser_ignores_comments_and_data_uri_commas(self) -> None:
        source = (
            '/* url("ignored.png"); @import "ignored.css"; */ '
            '.a { background: url(data:image/svg+xml;base64,PHN2Zy8+); } '
            '@import "local.css";'
        )
        self.assertEqual(
            parse_css_references(source),
            ["data:image/svg+xml;base64,PHN2Zy8+", "local.css"],
        )


class SiteFreshnessTests(unittest.TestCase):
    def test_source_selection_excludes_output_tests_and_docs(self) -> None:
        self.assertTrue(is_site_source_path(Path("main.tex")))
        self.assertTrue(is_site_source_path(Path("html/textbook-ui.js")))
        self.assertTrue(
            is_site_source_path(Path("statistics/topic/computations/analysis.html"))
        )
        self.assertFalse(is_site_source_path(Path("html/site/index.html")))
        self.assertFalse(is_site_source_path(Path("html/tests/test_ui.py")))
        self.assertFalse(is_site_source_path(Path("html/README.md")))

    def test_source_selection_uses_configured_output_directory(self) -> None:
        custom_output = Path("html/published-book")
        self.assertFalse(
            is_site_source_path(
                custom_output / "index.html",
                output_relative=custom_output,
            )
        )
        self.assertTrue(
            is_site_source_path(
                Path("html/site/index.html"),
                output_relative=custom_output,
            )
        )

    def test_fingerprint_is_deterministic_and_ignores_published_output(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            (root / "html" / "site").mkdir(parents=True)
            (root / "html" / "build.py").write_text("first", encoding="utf-8")
            (root / "html" / "site" / "index.html").write_text(
                "old site", encoding="utf-8"
            )
            candidates = [Path("html/build.py"), Path("html/site/index.html")]

            first = source_fingerprint(root, reversed(candidates))
            second = source_fingerprint(root, candidates)
            self.assertEqual(first, second)

            (root / "html" / "site" / "index.html").write_text(
                "different output", encoding="utf-8"
            )
            self.assertEqual(first, source_fingerprint(root, candidates))

            (root / "html" / "build.py").write_text("second", encoding="utf-8")
            self.assertNotEqual(first, source_fingerprint(root, candidates))

    def test_marker_verification_detects_stale_site(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            site = root / "html" / "site"
            site.mkdir(parents=True)
            source = root / "main.tex"
            source.write_text("version one", encoding="utf-8")
            candidates = [Path("main.tex")]

            digest = write_site_fingerprint(root, site, candidates)
            self.assertEqual(
                verify_site_fingerprint(root, site, candidates), digest
            )
            self.assertNotIn(
                "main.tex",
                (site / FINGERPRINT_FILENAME).read_text(encoding="ascii"),
            )

            source.write_text("version two", encoding="utf-8")
            with self.assertRaises(BuildError):
                verify_site_fingerprint(root, site, candidates)

    def test_temporary_marker_excludes_the_final_publication_directory(
        self,
    ) -> None:
        with ProjectTemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            site = root / "html" / "site"
            rendered = root / "html" / ".build" / "quarto" / "_site"
            site.mkdir(parents=True)
            rendered.mkdir(parents=True)
            (root / "main.tex").write_text("source", encoding="utf-8")
            (site / "index.html").write_text("old output", encoding="utf-8")
            candidates = [Path("main.tex"), Path("html/site/index.html")]

            write_site_fingerprint(
                root,
                rendered,
                candidates,
                output_dir=site,
            )
            shutil.copy2(
                rendered / FINGERPRINT_FILENAME,
                site / FINGERPRINT_FILENAME,
            )

            verify_site_fingerprint(root, site, candidates)

    def test_missing_marker_blocks_publication(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            site = root / "html" / "site"
            site.mkdir(parents=True)
            with self.assertRaises(BuildError):
                verify_site_fingerprint(root, site, [])


if __name__ == "__main__":
    unittest.main()
