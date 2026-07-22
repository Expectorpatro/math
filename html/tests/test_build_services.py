from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import tempfile
import unittest


HTML_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = HTML_DIR.parent

import sys

sys.path.insert(0, str(HTML_DIR))

from site_builder.config import BuildConfig
from site_builder.computations import ComputationImporter
from site_builder.errors import BuildError
from site_builder.filesystem import atomic_publish_directory
from site_builder.images import inspect_data_image, png_dimensions
from site_builder.models import QuartoPage
from site_builder.pandoc_transform import BookTransformer
from site_builder.postprocess import RenderedSitePostprocessor
from site_builder.quarto import build_chapter_navigation
from site_builder.qmd_writer import (
    collapse_excess_blank_lines,
    normalize_display_math,
)
from site_builder.validation import PageCollector, parse_srcset, validate_site


class ProjectTemporaryDirectory(tempfile.TemporaryDirectory[str]):
    """Keep all test writes inside the project's ignored build directory."""

    def __init__(self) -> None:
        root = HTML_DIR / ".build" / "tests"
        root.mkdir(parents=True, exist_ok=True)
        super().__init__(dir=root)


class ConfigTests(unittest.TestCase):
    def load_modified(self, transform) -> BuildConfig:
        with ProjectTemporaryDirectory() as temporary:
            root = Path(temporary)
            source = (HTML_DIR / "build-config.toml").read_text(encoding="utf-8")
            (root / "build-config.toml").write_text(
                transform(source), encoding="utf-8"
            )
            return BuildConfig.load(root)

    def test_rejects_generated_path_escape(self) -> None:
        with self.assertRaises(BuildError):
            self.load_modified(
                lambda source: source.replace(
                    'working_directory = ".build"',
                    'working_directory = ".."',
                )
            )

    def test_rejects_string_instead_of_boolean(self) -> None:
        with self.assertRaises(BuildError):
            self.load_modified(
                lambda source: source.replace(
                    "strict_broken_resources = true",
                    'strict_broken_resources = "false"',
                )
            )

    def test_rejects_unknown_configuration_field(self) -> None:
        with self.assertRaises(BuildError):
            self.load_modified(
                lambda source: source.replace(
                    "strict_broken_resources = true",
                    "strict_broken_resources = true\nstrcit_mode = true",
                )
            )

    def test_rejects_default_output_containing_build_workspace(self) -> None:
        with self.assertRaises(BuildError):
            self.load_modified(
                lambda source: source.replace(
                    'working_directory = ".build"',
                    'working_directory = "published/work"',
                ).replace(
                    'output_directory = "site"',
                    'output_directory = "published"',
                )
            )

    def test_rejects_requested_output_containing_build_workspace(self) -> None:
        config = self.load_modified(
            lambda source: source.replace(
                'working_directory = ".build"',
                'working_directory = "generated/work"',
            )
        )
        with self.assertRaises(BuildError):
            config.paths.resolve_output("generated")

    def test_central_config_loads(self) -> None:
        config = BuildConfig.load(HTML_DIR)
        self.assertEqual(config.assets.style_bundle, "style.css")
        self.assertEqual(len(config.assets.style_sources), 10)
        self.assertGreaterEqual(config.images.tikz_min_raster_width, 1920)


class ValidationTests(unittest.TestCase):
    def test_favicon_uses_one_shared_file_with_content_hash_query(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            (site / "chapters").mkdir()
            favicon = (
                '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'
            )
            (site / "favicon.svg").write_text(favicon, encoding="utf-8")
            (site / "index.html").write_text(
                '<link href="./favicon.svg?old" rel="icon">', encoding="utf-8"
            )
            chapter = site / "chapters" / "appendix.html"
            chapter.write_text(
                '<link href="../favicon.svg" rel="icon">', encoding="utf-8"
            )
            changed = RenderedSitePostprocessor._cache_bust_favicon(site)
            version = hashlib.sha256(favicon.encode()).hexdigest()[:12]
            self.assertEqual(changed, 2)
            self.assertFalse(any(site.glob("favicon-*.svg")))
            self.assertIn(
                f"./favicon.svg?v={version}",
                (site / "index.html").read_text(),
            )
            self.assertIn(f"../favicon.svg?v={version}", chapter.read_text())

    def test_srcset_parser_ignores_data_uri_commas(self) -> None:
        value = (
            "small.png 1x, data:image/svg+xml;base64,PHN2Zy8+ 2x, "
            "large.png 3x"
        )
        self.assertEqual(parse_srcset(value), ["small.png", "large.png"])
        collector = PageCollector()
        collector.feed(f'<img srcset="{value}" alt="">')
        self.assertEqual(
            [reference.target for reference in collector.references],
            ["small.png", "large.png"],
        )

    def test_report_uses_site_relative_paths_and_checks_fragments(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            (site / "index.html").write_text(
                '<a href="chapter.html#target">ok</a>', encoding="utf-8"
            )
            (site / "chapter.html").write_text(
                '<h1 id="target">Chapter</h1>', encoding="utf-8"
            )
            report = validate_site(site)
            self.assertFalse(report.has_errors)
            self.assertEqual(report.html_pages, 2)

    def test_postprocess_adds_image_metadata_and_unique_resource_ids(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAQAAABWKLW/AAAADElEQVR42mNk+A8AAQUB"
                "AScY42YAAAAASUVORK5CYII="
            )
            (site / "figure.png").write_bytes(png)
            markup = (
                "<html><head>"
                '<link id="quarto-bootstrap" class="quarto-color-scheme">'
                '<link id="quarto-bootstrap" class="quarto-color-scheme '
                'quarto-color-alternate">'
                '<link id="quarto-bootstrap" class="quarto-color-scheme-extra">'
                "</head><body>"
                '<img class="tikz-image" src="figure.png">'
                "</body></html>"
            )
            (site / "index.html").write_text(markup, encoding="utf-8")
            report = RenderedSitePostprocessor().process(
                site, {"repository": "https://example.invalid/book"}
            )
            updated = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn('width="2" height="3"', updated)
            self.assertIn('alt="TikZ 数学图示"', updated)
            collector = PageCollector()
            collector.feed(updated)
            self.assertFalse(collector.duplicate_resource_identifiers)
            self.assertEqual(report.image_alt_attributes_added, 1)
            self.assertEqual(report.image_dimension_pairs_added, 1)
            self.assertEqual(report.resource_ids_rewritten, 2)

    def test_postprocess_preserves_logical_width_aspect_ratio(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAQAAABWKLW/AAAADElEQVR42mNk+A8AAQUB"
                "AScY42YAAAAASUVORK5CYII="
            )
            (site / "figure.png").write_bytes(png)
            (site / "index.html").write_text(
                '<html><head></head><body><img src="figure.png" width="10">'
                "</body></html>",
                encoding="utf-8",
            )
            RenderedSitePostprocessor().process(
                site, {"repository": "https://example.invalid/book"}
            )
            updated = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn('width="10" height="15"', updated)


class PublicationTests(unittest.TestCase):
    def test_atomic_publish_replaces_a_managed_site(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "site"
            source.mkdir()
            destination.mkdir()
            (source / ".generated-site").write_text("", encoding="utf-8")
            (source / "index.html").write_text("new", encoding="utf-8")
            (destination / ".generated-site").write_text("", encoding="utf-8")
            (destination / "index.html").write_text("old", encoding="utf-8")
            warnings = atomic_publish_directory(
                source,
                destination,
                html_dir=root,
                protected=(),
            )
            self.assertEqual(warnings, ())
            self.assertEqual((destination / "index.html").read_text(), "new")

    def test_atomic_publish_refuses_unmanaged_destination(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "notes"
            source.mkdir()
            destination.mkdir()
            (source / ".generated-site").write_text("", encoding="utf-8")
            (destination / "personal.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(BuildError):
                atomic_publish_directory(
                    source,
                    destination,
                    html_dir=root,
                    protected=(),
                )

    def test_atomic_publish_migrates_recognized_legacy_site(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "site"
            source.mkdir()
            destination.mkdir()
            (source / ".generated-site").write_text("", encoding="utf-8")
            (source / "index.html").write_text("new", encoding="utf-8")
            (destination / ".nojekyll").write_text("", encoding="utf-8")
            (destination / "index.html").write_text("old", encoding="utf-8")
            (destination / "chapters").mkdir()
            (destination / "search.json").write_text("[]", encoding="utf-8")
            (destination / "sitemap.xml").write_text("", encoding="utf-8")
            atomic_publish_directory(
                source,
                destination,
                html_dir=root,
                protected=(),
            )
            self.assertEqual((destination / "index.html").read_text(), "new")
            self.assertTrue((destination / ".generated-site").is_file())

    def test_atomic_publish_rejects_destination_containing_protected_path(self) -> None:
        with ProjectTemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "site"
            source.mkdir()
            (source / ".generated-site").write_text("", encoding="utf-8")
            (source / "index.html").write_text("new", encoding="utf-8")
            with self.assertRaises(BuildError):
                atomic_publish_directory(
                    source,
                    destination,
                    html_dir=root,
                    protected=(destination / ".build",),
                )


class ImageAndNavigationTests(unittest.TestCase):
    def test_figures_receive_visible_chapter_numbers(self) -> None:
        transformer = BookTransformer({}, {}, [], {})
        transformer.chapter = 1
        figure = {
            "t": "Figure",
            "c": [
                ["", [], []],
                [None, [{"t": "Plain", "c": [{"t": "Str", "c": "示意图"}]}]],
                [{"t": "Plain", "c": []}],
            ],
        }
        transformed = transformer.process_blocks([figure])[0]
        attribute, caption, _body = transformed["c"]
        self.assertEqual(attribute[0], "fig-1-1")
        self.assertIn("textbook-figure", attribute[1])
        self.assertEqual(transformer.labels["fig-1-1"], ("图", "1.1"))
        number = caption[1][0]["c"][0]
        self.assertEqual(number["c"][0][1], ["figure-number"])
        self.assertEqual(number["c"][1][0]["c"], "图 1.1")

    def test_inspects_actual_png_dimensions(self) -> None:
        encoded = (
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAQAAABWKLW/AAAADElEQVR42mNk+A8AAQUB"
            "AScY42YAAAAASUVORK5CYII="
        )
        data = base64.b64decode(encoded)
        dimensions = png_dimensions(data)
        self.assertIsNotNone(dimensions)
        assert dimensions is not None
        self.assertEqual((dimensions.width, dimensions.height), (2, 3))
        info = inspect_data_image("image/png", encoded, "unit-test")
        self.assertEqual((info.width, info.height), (2, 3))
        self.assertFalse(info.vector)

    def test_computation_images_receive_accessible_fallback_text(self) -> None:
        importer = ComputationImporter(
            project_root=PROJECT_ROOT,
            quarto_project_dir=HTML_DIR / ".build" / "test-quarto",
        )
        svg = "PHN2ZyB2aWV3Qm94PSIwIDAgMTAgNSI+PHBhdGggZD0iTTAgMGgxMHY1eiIvPjwvc3ZnPg=="
        fragment = importer.prefix_identifiers(
            f'<img role="img" src="data:image/svg+xml;base64,{svg}">',
            "case-",
        )
        self.assertIn('alt="计算结果图（图 1）"', fragment)

    def test_chapter_navigation_groups_consecutive_parts(self) -> None:
        pages = [
            QuartoPage(Path("chapters/a.qmd"), [], "第一部分"),
            QuartoPage(Path("chapters/b.qmd"), [], "第一部分"),
            QuartoPage(Path("references.qmd"), [], None),
        ]
        navigation = build_chapter_navigation(pages)
        self.assertEqual(navigation[0], "index.qmd")
        self.assertEqual(
            navigation[1],
            {
                "part": "第一部分",
                "chapters": ["chapters/a.qmd", "chapters/b.qmd"],
            },
        )

    def test_display_math_normalizer_preserves_fenced_code(self) -> None:
        pattern = r"^(?P<indent>[ \t]*)(?:\d+[.)]|[-+*])(?P<space>[ \t]+)"
        markdown = (
            "```python\nprint('$$ untouched $$')\n```\n\n"
            "~~~text\n$$also untouched$$\n~~~\n\n"
            "A sentence $$x + y$$ after text.\n"
        )
        normalized = normalize_display_math(markdown, pattern)
        self.assertIn("print('$$ untouched $$')", normalized)
        self.assertIn("$$also untouched$$", normalized)
        self.assertIn("\n$$\nx + y\n$$\n", normalized)

    def test_blank_line_cleanup_preserves_fenced_code(self) -> None:
        markdown = (
            "First paragraph.\n\n\n\nSecond paragraph.\n\n"
            "```python\nfirst = 1\n\n\n\nsecond = 2\n```\n\n\n"
            "Last paragraph.\n"
        )
        cleaned = collapse_excess_blank_lines(markdown)
        self.assertIn("First paragraph.\n\nSecond paragraph.", cleaned)
        self.assertIn("first = 1\n\n\n\nsecond = 2", cleaned)
        self.assertIn("```\n\nLast paragraph.", cleaned)


if __name__ == "__main__":
    unittest.main()
