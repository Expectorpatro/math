"""Typed, centralized configuration for the HTML build.

All paths are derived from the checked-in ``build-config.toml`` and the
location of the ``html`` directory. Callers never need to duplicate temporary
directory names, image resolution settings, or tool fallbacks.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import shutil
import tomllib
from typing import Any, Mapping

from .errors import BuildError


def _mapping(value: Any, section: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise BuildError(f"build-config.toml 的 [{section}] 必须是表")
    return value


def _positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise BuildError(f"build-config.toml 的 {name} 必须是正整数")
    return value


def _positive_float(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise BuildError(f"build-config.toml 的 {name} 必须是正数")
    result = float(value)
    if not math.isfinite(result):
        raise BuildError(f"build-config.toml 的 {name} 必须是有限正数")
    return result


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuildError(f"build-config.toml 的 {name} 必须是非空字符串")
    return value.strip()


def _generated_path(parent: Path, value: Any, name: str) -> Path:
    """Resolve a configured generated path and keep it below *parent*."""

    relative = Path(_nonempty_string(value, name))
    if relative.is_absolute():
        raise BuildError(f"build-config.toml 的 {name} 必须是相对路径")
    destination = (parent / relative).resolve()
    try:
        inside = destination.relative_to(parent.resolve())
    except ValueError as error:
        raise BuildError(f"build-config.toml 的 {name} 不能越出生成目录") from error
    if not inside.parts:
        raise BuildError(f"build-config.toml 的 {name} 不能指向父目录本身")
    return destination


def _paths_overlap(first: Path, second: Path) -> bool:
    """Return whether either resolved path contains the other."""

    first = first.resolve()
    second = second.resolve()
    return (
        first == second
        or first.is_relative_to(second)
        or second.is_relative_to(first)
    )


def _string_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise BuildError(f"build-config.toml 的 {name} 必须是非空字符串列表")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise BuildError(f"build-config.toml 的 {name} 只能包含非空字符串")
    result = tuple(item.strip() for item in value)
    if len(set(result)) != len(result):
        raise BuildError(f"build-config.toml 的 {name} 不得包含重复项")
    return result


@dataclass(frozen=True, slots=True)
class BuildPaths:
    """Absolute paths used by one build invocation."""

    html_dir: Path
    project_root: Path
    config_file: Path
    build_dir: Path
    staged_source_dir: Path
    quarto_project_dir: Path
    cache_dir: Path
    tikz_work_dir: Path
    quarto_cache_dir: Path
    deno_cache_dir: Path
    xdg_cache_dir: Path
    xdg_config_dir: Path
    xdg_data_dir: Path
    default_output_dir: Path

    @property
    def main_tex(self) -> Path:
        return self.project_root / "main.tex"

    @property
    def settings_tex(self) -> Path:
        return self.project_root / "settings.tex"

    @property
    def home_source(self) -> Path:
        return self.html_dir / "content" / "home.md"

    @property
    def site_metadata_file(self) -> Path:
        return self.html_dir / "data" / "site-meta.json"

    @property
    def chapter_progress_file(self) -> Path:
        return self.html_dir / "data" / "chapter-progress.json"

    @property
    def notation_catalog_file(self) -> Path:
        return self.html_dir / "data" / "notation-catalog.json"

    def html_asset(self, name: str) -> Path:
        """Return a checked-in asset path inside ``html/``."""

        path = (self.html_dir / name).resolve()
        try:
            path.relative_to(self.html_dir)
        except ValueError as error:
            raise BuildError(f"HTML 资源路径越界：{name}") from error
        return path

    def resolve_output(self, value: str | Path) -> Path:
        """Resolve and validate a user-selected publication directory.

        Output must be a strict child of ``html/`` and may not overlap the
        build workspace.  This prevents an output typo from deleting sources
        or self-deleting a live Quarto project.
        """

        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.html_dir / candidate
        candidate = candidate.resolve()
        try:
            relative = candidate.relative_to(self.html_dir)
        except ValueError as error:
            raise BuildError("输出目录必须位于 html/ 内") from error
        if not relative.parts:
            raise BuildError("输出目录不能是 html/ 本身")
        if _paths_overlap(candidate, self.build_dir):
            raise BuildError("输出目录不能与 HTML 构建工作目录重叠")
        protected_names = {
            "assets",
            "content",
            "data",
            "scripts",
            "site_builder",
            "styles",
            "templates",
        }
        if relative.parts[0] in protected_names or candidate.suffix:
            raise BuildError(f"输出目录与 HTML 源代码重叠：{relative}")
        return candidate


@dataclass(frozen=True, slots=True)
class ToolConfig:
    """Command names and the local Quarto fallback used by the build."""

    quarto_fallback: Path
    pandoc: str
    xelatex: str
    ghostscript: str
    git: str

    def quarto_path(self) -> Path:
        configured = os.environ.get("QUARTO")
        if configured:
            return Path(configured).expanduser().resolve()
        discovered = shutil.which("quarto")
        if discovered:
            return Path(discovered).resolve()
        return self.quarto_fallback


@dataclass(frozen=True, slots=True)
class ImageQuality:
    """Quality policy for generated images only.

    File-backed images supplied by authors are deliberately outside this
    policy: the build copies them byte-for-byte and never resamples them.
    """

    tikz_raster_dpi: int
    tikz_min_raster_width: int
    tikz_max_raster_dpi: int
    tikz_border_points: float
    computation_min_raster_width: int
    computation_min_pixel_ratio: float


@dataclass(frozen=True, slots=True)
class RenderConfig:
    language: str
    toc_depth: int
    sidebar_width_px: int
    body_width_px: int
    margin_width_px: int
    gutter_rem: float


@dataclass(frozen=True, slots=True)
class AssetConfig:
    public_sources: tuple[str, ...]
    citation_style_source: str
    style_bundle: str
    style_sources: tuple[str, ...]
    header_template_source: str

    @property
    def public_files(self) -> tuple[str, ...]:
        return tuple(Path(source).name for source in self.public_sources)

    @property
    def citation_style(self) -> str:
        return Path(self.citation_style_source).name

    @property
    def header_template(self) -> str:
        return Path(self.header_template_source).name


@dataclass(frozen=True, slots=True)
class BuildConfig:
    """Complete immutable configuration for a website build."""

    paths: BuildPaths
    tools: ToolConfig
    images: ImageQuality
    render: RenderConfig
    assets: AssetConfig

    @classmethod
    def load(cls, html_dir: Path) -> "BuildConfig":
        html_dir = html_dir.resolve()
        config_file = html_dir / "build-config.toml"
        try:
            raw = tomllib.loads(config_file.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise BuildError(f"找不到 HTML 构建配置：{config_file}") from error
        except tomllib.TOMLDecodeError as error:
            raise BuildError(f"build-config.toml 格式错误：{error}") from error

        unknown_sections = sorted(
            set(raw).difference({"build", "tools", "images", "render", "assets"})
        )
        if unknown_sections:
            raise BuildError(
                "build-config.toml 包含未知配置节："
                + "、".join(unknown_sections)
            )

        build = _mapping(raw.get("build"), "build")
        tools = _mapping(raw.get("tools"), "tools")
        images = _mapping(raw.get("images"), "images")
        render = _mapping(raw.get("render"), "render")
        assets = _mapping(raw.get("assets"), "assets")

        required_keys = {
            "build": (
                build,
                {
                    "output_directory",
                    "working_directory",
                    "staged_source_directory",
                    "quarto_project_directory",
                    "cache_directory",
                },
            ),
            "tools": (
                tools,
                {"quarto_fallback", "pandoc", "xelatex", "ghostscript", "git"},
            ),
            "images": (
                images,
                {
                    "tikz_raster_dpi",
                    "tikz_min_raster_width",
                    "tikz_max_raster_dpi",
                    "tikz_border_points",
                    "computation_min_raster_width",
                    "computation_min_pixel_ratio",
                },
            ),
            "render": (
                render,
                {
                    "language",
                    "toc_depth",
                    "sidebar_width_px",
                    "body_width_px",
                    "margin_width_px",
                    "gutter_rem",
                },
            ),
            "assets": (
                assets,
                {
                    "public_sources",
                    "citation_style_source",
                    "style_bundle",
                    "style_sources",
                    "header_template_source",
                },
            ),
        }
        for section, (values, expected) in required_keys.items():
            missing = sorted(expected.difference(values))
            if missing:
                raise BuildError(
                    f"build-config.toml 的 [{section}] 缺少字段："
                    + "、".join(missing)
                )
            unknown = sorted(set(values).difference(expected))
            if unknown:
                raise BuildError(
                    f"build-config.toml 的 [{section}] 包含未知字段："
                    + "、".join(unknown)
                )

        build_dir = _generated_path(
            html_dir, build["working_directory"], "build.working_directory"
        )
        cache_dir = _generated_path(
            build_dir, build["cache_directory"], "build.cache_directory"
        )
        staged_source_dir = _generated_path(
            build_dir,
            build["staged_source_directory"],
            "build.staged_source_directory",
        )
        quarto_project_dir = _generated_path(
            build_dir,
            build["quarto_project_directory"],
            "build.quarto_project_directory",
        )
        tikz_work_dir = _generated_path(
            build_dir, "tikz-work", "内部 TikZ 工作目录"
        )
        generated_roots = (
            cache_dir,
            staged_source_dir,
            quarto_project_dir,
            tikz_work_dir,
        )
        for index, first in enumerate(generated_roots):
            for second in generated_roots[index + 1 :]:
                try:
                    first.relative_to(second)
                except ValueError:
                    try:
                        second.relative_to(first)
                    except ValueError:
                        continue
                raise BuildError("HTML 生成目录之间不得相互包含")
        default_output_dir = _generated_path(
            html_dir,
            build["output_directory"],
            "build.output_directory",
        )
        if _paths_overlap(default_output_dir, build_dir):
            raise BuildError("默认输出目录不能与 HTML 构建工作目录重叠")

        paths = BuildPaths(
            html_dir=html_dir,
            project_root=html_dir.parent,
            config_file=config_file,
            build_dir=build_dir,
            staged_source_dir=staged_source_dir,
            quarto_project_dir=quarto_project_dir,
            cache_dir=cache_dir,
            tikz_work_dir=tikz_work_dir,
            quarto_cache_dir=cache_dir / "quarto",
            deno_cache_dir=cache_dir / "deno",
            xdg_cache_dir=cache_dir / "xdg-cache",
            xdg_config_dir=cache_dir / "xdg-config",
            xdg_data_dir=cache_dir / "xdg-data",
            default_output_dir=default_output_dir,
        )

        return cls(
            paths=paths,
            tools=ToolConfig(
                quarto_fallback=Path(
                    _nonempty_string(
                        tools["quarto_fallback"], "tools.quarto_fallback"
                    )
                ).expanduser(),
                pandoc=_nonempty_string(tools["pandoc"], "tools.pandoc"),
                xelatex=_nonempty_string(tools["xelatex"], "tools.xelatex"),
                ghostscript=_nonempty_string(
                    tools["ghostscript"], "tools.ghostscript"
                ),
                git=_nonempty_string(tools["git"], "tools.git"),
            ),
            images=ImageQuality(
                tikz_raster_dpi=_positive_int(
                    images["tikz_raster_dpi"], "images.tikz_raster_dpi"
                ),
                tikz_min_raster_width=_positive_int(
                    images["tikz_min_raster_width"],
                    "images.tikz_min_raster_width",
                ),
                tikz_max_raster_dpi=_positive_int(
                    images["tikz_max_raster_dpi"],
                    "images.tikz_max_raster_dpi",
                ),
                tikz_border_points=_positive_float(
                    images["tikz_border_points"], "images.tikz_border_points"
                ),
                computation_min_raster_width=_positive_int(
                    images["computation_min_raster_width"],
                    "images.computation_min_raster_width",
                ),
                computation_min_pixel_ratio=_positive_float(
                    images["computation_min_pixel_ratio"],
                    "images.computation_min_pixel_ratio",
                ),
            ),
            render=RenderConfig(
                language=_nonempty_string(render["language"], "render.language"),
                toc_depth=_positive_int(render["toc_depth"], "render.toc_depth"),
                sidebar_width_px=_positive_int(
                    render["sidebar_width_px"], "render.sidebar_width_px"
                ),
                body_width_px=_positive_int(
                    render["body_width_px"], "render.body_width_px"
                ),
                margin_width_px=_positive_int(
                    render["margin_width_px"], "render.margin_width_px"
                ),
                gutter_rem=_positive_float(
                    render["gutter_rem"], "render.gutter_rem"
                ),
            ),
            assets=AssetConfig(
                public_sources=_string_tuple(
                    assets["public_sources"], "assets.public_sources"
                ),
                citation_style_source=_nonempty_string(
                    assets["citation_style_source"],
                    "assets.citation_style_source",
                ),
                style_bundle=_nonempty_string(
                    assets["style_bundle"], "assets.style_bundle"
                ),
                style_sources=_string_tuple(
                    assets["style_sources"], "assets.style_sources"
                ),
                header_template_source=_nonempty_string(
                    assets["header_template_source"],
                    "assets.header_template_source",
                ),
            ),
        )
