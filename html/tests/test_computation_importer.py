"""Security and image-quality contracts for imported computation HTML."""

from __future__ import annotations

import base64
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock


HTML_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = HTML_DIR.parent
sys.path.insert(0, str(HTML_DIR))

from site_builder.computations import ComputationImporter
from site_builder.errors import BuildError


def png_data_uri(width: int, height: int) -> str:
    """Return the smallest PNG header understood by the image inspector."""

    header = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
    )
    return "data:image/png;base64," + base64.b64encode(header).decode("ascii")


def jpeg_data_uri(width: int, height: int) -> str:
    """Return a minimal JPEG SOF header understood by the image inspector."""

    header = (
        b"\xff\xd8\xff\xc0\x00\x07\x08"
        + struct.pack(">H", height)
        + struct.pack(">H", width)
    )
    return "data:image/jpeg;base64," + base64.b64encode(header).decode("ascii")


def svg_data_uri() -> str:
    source = '<svg viewBox="0 0 10 5"><path d="M0 0h10v5z"/></svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(
        source.encode("utf-8")
    ).decode("ascii")


class ComputationImporterSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.importer = ComputationImporter(
            project_root=PROJECT_ROOT,
            quarto_project_dir=HTML_DIR / ".build" / "test-quarto",
            minimum_raster_width=100,
        )

    def rewrite(self, fragment: str) -> str:
        return self.importer.prefix_identifiers(fragment, "case-")

    def test_rejects_active_elements(self) -> None:
        fragments = {
            "iframe": "<iframe></iframe>",
            "object": "<object></object>",
            "embed": "<embed>",
            "foreignObject": "<svg><foreignObject></foreignObject></svg>",
            "animate": "<svg><animate></animate></svg>",
            "set": "<svg><set></set></svg>",
            "applet": "<applet></applet>",
            "frame": "<frame/>",
            "frameset": "<frameset></frameset>",
            "fencedframe": "<fencedframe></fencedframe>",
            "portal": "<portal></portal>",
            "script": "<script>alert(1)</script>",
            "form": "<form></form>",
        }
        for element_name, fragment in fragments.items():
            with self.subTest(element=element_name):
                with self.assertRaisesRegex(BuildError, "不允许的活动元素"):
                    self.rewrite(fragment)

    def test_rejects_active_attributes(self) -> None:
        fragments = {
            "srcdoc": (
                '<div srcdoc="&lt;script&gt;alert(1)&lt;/script&gt;"></div>'
            ),
            "formaction": (
                '<button formaction="https://example.com">send</button>'
            ),
            "ping": (
                '<a href="https://example.com" '
                'ping="https://tracker.invalid">link</a>'
            ),
            "autoplay": "<video autoplay></video>",
            "event": '<div onmouseover="alert(1)">text</div>',
        }
        for attribute_name, fragment in fragments.items():
            with self.subTest(attribute=attribute_name):
                with self.assertRaisesRegex(BuildError, "不允许的.*属性"):
                    self.rewrite(fragment)

    def test_rejects_unvalidated_href_on_svg_elements(self) -> None:
        with self.assertRaises(BuildError):
            self.rewrite(
                '<svg viewBox="0 0 10 10">'
                '<textPath href="https://example.com/object.svg#shape">x</textPath>'
                "</svg>"
            )

    def test_svg_use_only_accepts_local_fragments(self) -> None:
        with self.assertRaisesRegex(BuildError, "必须指向当前片段"):
            self.rewrite(
                '<svg viewBox="0 0 10 10">'
                f'<use href="{svg_data_uri()}"></use>'
                "</svg>"
            )

    def test_rejects_external_url_in_any_svg_paint_attribute(self) -> None:
        with self.assertRaisesRegex(BuildError, "未嵌入或外部资源"):
            self.rewrite(
                '<svg viewBox="0 0 10 10">'
                '<rect width="10" height="10" '
                'fill="url(https://example.invalid/paint.svg#gradient)"></rect>'
                "</svg>"
            )

    def test_rejects_resource_attribute_without_value(self) -> None:
        with self.assertRaisesRegex(BuildError, "空资源属性"):
            self.rewrite("<img src>")

    def test_accepts_typical_static_quarto_output(self) -> None:
        fragment = (
            '<section class="cell">'
            '<style scoped>.dataframe { color: inherit; }</style>'
            '<h2 id="result">Result</h2>'
            '<div class="cell-output">'
            '<table class="dataframe"><tbody><tr>'
            "<th>x</th><td>1</td></tr></tbody></table>"
            '<pre><code>print(1)</code></pre>'
            '<button type="button" class="code-copy-button">Copy</button>'
            '<svg viewBox="0 0 10 5"><defs><path id="curve" d="M0 0h10"/></defs>'
            '<use xlink:href="#curve"></use></svg>'
            f'<img src="{svg_data_uri()}">'
            "</div></section>"
        )

        rewritten = self.rewrite(fragment)

        self.assertIn('id="case-result"', rewritten)
        self.assertIn('xlink:href="#case-curve"', rewritten)
        self.assertIn("code-copy-button", rewritten)
        self.assertIn("dataframe", rewritten)
        self.assertNotIn("<style", rewritten)


class ComputationImporterImageQualityTests(unittest.TestCase):
    def importer(
        self,
        minimum: int,
        *,
        pixel_ratio: float = 1.0,
    ) -> ComputationImporter:
        return ComputationImporter(
            project_root=PROJECT_ROOT,
            quarto_project_dir=HTML_DIR / ".build" / "test-quarto",
            minimum_raster_width=minimum,
            minimum_pixel_ratio=pixel_ratio,
        )

    def test_rejects_png_below_configured_minimum_width(self) -> None:
        source = png_data_uri(99, 60)
        with self.assertRaisesRegex(BuildError, "99px.*100px"):
            self.importer(100).prefix_identifiers(
                f'<img src="{source}">', "case-"
            )

    def test_rejects_jpeg_below_configured_minimum_width(self) -> None:
        source = jpeg_data_uri(119, 80)
        with self.assertRaisesRegex(BuildError, "119px.*120px"):
            self.importer(120).prefix_identifiers(
                f'<img src="{source}">', "case-"
            )

    def test_accepts_raster_at_minimum_without_publishing_diagnostics(self) -> None:
        source = png_data_uri(100, 60)
        rewritten = self.importer(100).prefix_identifiers(
            f'<img src="{source}">', "case-"
        )

        self.assertIn(source, rewritten)
        self.assertIn('alt="计算结果图（图 1）"', rewritten)
        self.assertNotIn("width=", rewritten)
        self.assertNotIn("height=", rewritten)
        self.assertNotIn("分辨率", rewritten)

    def test_allows_svg_regardless_of_raster_minimum(self) -> None:
        source = svg_data_uri()
        rewritten = self.importer(10_000).prefix_identifiers(
            f'<img src="{source}">', "case-"
        )
        self.assertIn(source, rewritten)

    def test_srcset_uses_the_largest_embedded_candidate(self) -> None:
        small = png_data_uri(100, 40)
        large = png_data_uri(200, 80)
        rewritten = self.importer(1_000, pixel_ratio=2).prefix_identifiers(
            f'<img width="100" src="{small}" '
            f'srcset="{small} 1x, {large} 2x">',
            "case-",
        )
        self.assertIn('width="100"', rewritten)

    def test_srcset_rejects_candidate_that_lies_about_density(self) -> None:
        small = png_data_uri(100, 40)
        fake_retina = png_data_uri(150, 80)
        with self.assertRaisesRegex(BuildError, "小于其 x 描述符"):
            self.importer(1, pixel_ratio=2).prefix_identifiers(
                f'<img width="100" src="{small}" '
                f'srcset="{small} 1x, {fake_retina} 2x">',
                "case-",
            )

    def test_vector_high_candidate_does_not_hide_invalid_raster_candidate(
        self,
    ) -> None:
        blurry = png_data_uri(80, 40)
        vector = svg_data_uri()
        with self.assertRaisesRegex(BuildError, "小于其 x 描述符"):
            self.importer(1, pixel_ratio=2).prefix_identifiers(
                f'<img width="100" src="{blurry}" '
                f'srcset="{blurry} 1x, {vector} 2x">',
                "case-",
            )

    def test_vector_high_candidate_does_not_bypass_fallback_width(self) -> None:
        blurry = png_data_uri(99, 40)
        vector = svg_data_uri()
        with self.assertRaisesRegex(BuildError, "质量下限"):
            self.importer(100).prefix_identifiers(
                f'<picture><source srcset="{blurry} 1x, {vector} 2x">'
                f'<img src="{vector}"></picture>',
                "case-",
            )

    def test_picture_source_uses_raster_quality_policy(self) -> None:
        source = png_data_uri(99, 60)
        with self.assertRaisesRegex(BuildError, "质量下限"):
            self.importer(100).prefix_identifiers(
                f'<picture><source srcset="{source} 1x">'
                f'<img src="{svg_data_uri()}"></picture>',
                "case-",
            )

    def test_svg_image_raster_uses_declared_logical_width(self) -> None:
        source = png_data_uri(199, 80)
        with self.assertRaisesRegex(BuildError, r"1\.99x.*2x"):
            self.importer(1, pixel_ratio=2).prefix_identifiers(
                '<svg viewBox="0 0 100 40">'
                f'<image width="100" height="40" href="{source}"></image>'
                "</svg>",
                "case-",
            )

    def test_css_embedded_raster_uses_absolute_fallback(self) -> None:
        source = png_data_uri(99, 60)
        with self.assertRaisesRegex(BuildError, "99px.*100px"):
            self.importer(100).prefix_identifiers(
                f'<div style="background-image:url({source})"></div>',
                "case-",
            )

    def test_width_srcset_checks_declared_candidate_width(self) -> None:
        small = png_data_uri(100, 40)
        large = png_data_uri(200, 80)
        rewritten = self.importer(1_000, pixel_ratio=2).prefix_identifiers(
            f'<img width="100" src="{small}" '
            f'srcset="{small} 100w, {large} 200w">',
            "case-",
        )
        self.assertIn("200w", rewritten)

    def test_embedded_image_is_decoded_once_per_element(self) -> None:
        source = png_data_uri(200, 80)
        with mock.patch(
            "site_builder.computations.inspect_data_image",
            wraps=__import__(
                "site_builder.computations",
                fromlist=["inspect_data_image"],
            ).inspect_data_image,
        ) as inspector:
            self.importer(1, pixel_ratio=2).prefix_identifiers(
                f'<img width="100" src="{source}">', "case-"
            )
        self.assertEqual(inspector.call_count, 1)

    def test_rejects_raster_below_declared_pixel_ratio(self) -> None:
        source = png_data_uri(199, 80)
        with self.assertRaisesRegex(BuildError, r"1\.99x.*2x"):
            self.importer(1, pixel_ratio=2).prefix_identifiers(
                f'<img width="100" src="{source}">', "case-"
            )

    def test_declared_pixel_ratio_overrides_absolute_fallback(self) -> None:
        source = png_data_uri(200, 80)
        rewritten = self.importer(
            1_000,
            pixel_ratio=2,
        ).prefix_identifiers(
            f'<img width="100" src="{source}">', "case-"
        )
        self.assertIn(source, rewritten)

    def test_rejects_invalid_declared_width(self) -> None:
        source = png_data_uri(200, 80)
        with self.assertRaisesRegex(BuildError, "width 必须是正整数"):
            self.importer(1, pixel_ratio=2).prefix_identifiers(
                f'<img width="100%" src="{source}">', "case-"
            )

    def test_rejects_nonpositive_minimum(self) -> None:
        with self.assertRaises(ValueError):
            self.importer(0)

    def test_rejects_nonpositive_pixel_ratio(self) -> None:
        with self.assertRaises(ValueError):
            self.importer(1, pixel_ratio=0)


if __name__ == "__main__":
    unittest.main()
