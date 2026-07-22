#!/usr/bin/env python3
"""Build the LaTeX textbook as a multi-page HTML site.

The LaTeX sources remain the single source of truth.  This script stages copies
of the .tex files, lets Pandoc parse them into its JSON AST, applies the
project-specific theorem/glossary/reference rules, and asks Quarto to render a
structured static book.
"""

from __future__ import annotations

import argparse
from collections import Counter
from functools import partial
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from site_builder.errors import BuildError

try:
    from site_builder.assets import AssetManager
    from site_builder.commands import CommandRunner
    from site_builder.computation_orders import load_computation_orders
    from site_builder.computations import ComputationImporter
    from site_builder.config import BuildConfig
    from site_builder.filesystem import (
        atomic_publish_directory,
        prepare_empty_directory,
    )
    from site_builder.freshness import write_site_fingerprint
    from site_builder.latex_sources import (
        load_glossary,
        parse_theorem_specs,
        stage_sources,
    )
    from site_builder.metadata import (
        load_chapter_progress,
        load_notation_catalog,
        load_site_metadata,
    )
    from site_builder.models import ComputationGroup
    from site_builder.pandoc_transform import (
        BookTransformer,
        ast_plain_text,
        parse_latex_to_ast,
    )
    from site_builder.pages import (
        add_reference_page,
        collect_identifiers,
        rewrite_quarto_targets,
        sanitize_quarto_identifiers,
        split_quarto_pages,
    )
    from site_builder.postprocess import (
        PostprocessReport,
        RenderedSitePostprocessor,
    )
    from site_builder.qmd_writer import write_qmd_page
    from site_builder.site_content import write_quarto_config
    from site_builder.validation import validate_site as validate_rendered_site

    HTML_DIR = Path(__file__).resolve().parent
    CONFIG = BuildConfig.load(HTML_DIR)
    RUNNER = CommandRunner()
except BuildError as error:
    if __name__ == "__main__":
        print(f"[web] 错误：{error}", file=sys.stderr)
        raise SystemExit(1) from None
    raise

PROJECT_ROOT = CONFIG.paths.project_root
MAIN_TEX = CONFIG.paths.main_tex
SETTINGS_TEX = CONFIG.paths.settings_tex
QUARTO = CONFIG.tools.quarto_path()
QUARTO_PROJECT_DIR = CONFIG.paths.quarto_project_dir
ASSET_MANAGER = AssetManager(CONFIG, RUNNER)
COMPUTATION_IMPORTER = ComputationImporter(
    project_root=PROJECT_ROOT,
    quarto_project_dir=QUARTO_PROJECT_DIR,
    minimum_raster_width=CONFIG.images.computation_min_raster_width,
    minimum_pixel_ratio=CONFIG.images.computation_min_pixel_ratio,
    logger=RUNNER.log,
)
SITE_POSTPROCESSOR = RenderedSitePostprocessor(RUNNER.warning)


def log(message: str) -> None:
    RUNNER.log(message)


def fail(message: str) -> None:
    raise BuildError(message)


def run(
    command: list[str],
    *,
    cwd: Path,
    input_text: str | None = None,
    environment: dict[str, str] | None = None,
) -> str:
    return RUNNER.run(
        command,
        cwd=cwd,
        input_text=input_text,
        environment=environment,
    )


def ensure_tool(name: str) -> None:
    RUNNER.require(name)


def copy_quarto_resources(document: dict[str, Any]) -> None:
    """Build and copy the validated resource manifest for Quarto."""

    manifest = ASSET_MANAGER.prepare(document)
    log(f"已准备 {len(manifest)} 个网页资源")


def write_quarto_site(
    document: dict[str, Any],
    transformer: BookTransformer,
    computation_orders: dict[str, list[ComputationGroup]],
    site_metadata: dict[str, str],
    chapter_progress: dict[str, int | None],
    notation_catalog: dict[str, Any],
) -> tuple[Path, PostprocessReport]:
    if not QUARTO.exists():
        fail(
            "找不到 Quarto。可通过环境变量 QUARTO 指定可执行文件，"
            f"当前路径：{QUARTO}"
        )
    prepare_empty_directory(
        QUARTO_PROJECT_DIR,
        managed=(QUARTO_PROJECT_DIR,),
    )

    sanitize_quarto_identifiers(document)
    copy_quarto_resources(document)
    pages = split_quarto_pages(document, transformer)
    add_reference_page(pages)
    page_path_counts = Counter(page.source_path for page in pages)
    duplicate_page_paths = sorted(
        str(path) for path, count in page_path_counts.items() if count > 1
    )
    if duplicate_page_paths:
        fail("多个章节生成了同一页面路径：" + "、".join(duplicate_page_paths))
    expected_progress_keys = {
        page.source_path.stem
        for page in pages
        if page.part not in {None, "中英术语表"}
    }
    configured_progress_keys = set(chapter_progress)
    if expected_progress_keys != configured_progress_keys:
        missing = sorted(expected_progress_keys - configured_progress_keys)
        unknown = sorted(configured_progress_keys - expected_progress_keys)
        details: list[str] = []
        if missing:
            details.append("缺少：" + "、".join(missing))
        if unknown:
            details.append("未知：" + "、".join(unknown))
        fail(
            f"chapter-progress.json 必须与正文 {len(expected_progress_keys)} 章"
            "完全一致（" + "；".join(details) + "）"
        )
    labels_to_pages: dict[str, Path] = {}
    for page in pages:
        identifiers: set[str] = set()
        collect_identifiers(page.blocks, identifiers)
        for identifier in identifiers:
            previous_page = labels_to_pages.get(identifier)
            if previous_page is not None and previous_page != page.source_path:
                fail(
                    f"跨页面重复标识符 {identifier!r}："
                    f"{previous_page} 与 {page.source_path}"
                )
            labels_to_pages[identifier] = page.source_path
    for page in pages:
        page.blocks = rewrite_quarto_targets(
            page.blocks,
            page.source_path,
            labels_to_pages,
        )
        write_qmd_page(
            page,
            document,
            chapter_progress,
            config=CONFIG,
            runner=RUNNER,
        )

    computation_appendices = COMPUTATION_IMPORTER.build_appendices(
        pages,
        computation_orders,
        plain_text=ast_plain_text,
    )

    write_quarto_config(
        document,
        pages,
        transformer,
        site_metadata,
        chapter_progress,
        notation_catalog,
        config=CONFIG,
    )
    runtime_directories = (
        CONFIG.paths.quarto_cache_dir,
        CONFIG.paths.deno_cache_dir,
        CONFIG.paths.xdg_cache_dir,
        CONFIG.paths.xdg_config_dir,
        CONFIG.paths.xdg_data_dir,
    )
    for directory in runtime_directories:
        directory.mkdir(parents=True, exist_ok=True)
    run(
        [str(QUARTO), "render"],
        cwd=QUARTO_PROJECT_DIR,
        environment={
            "QUARTO_CACHE_DIR": str(CONFIG.paths.quarto_cache_dir),
            "DENO_DIR": str(CONFIG.paths.deno_cache_dir),
            "XDG_CACHE_HOME": str(CONFIG.paths.xdg_cache_dir),
            "XDG_CONFIG_HOME": str(CONFIG.paths.xdg_config_dir),
            "XDG_DATA_HOME": str(CONFIG.paths.xdg_data_dir),
        },
    )

    COMPUTATION_IMPORTER.append_to_site(
        computation_appendices, QUARTO_PROJECT_DIR / "_site"
    )

    rendered_site = QUARTO_PROJECT_DIR / "_site"
    postprocess_report = SITE_POSTPROCESSOR.process(
        rendered_site, site_metadata
    )
    (rendered_site / ".nojekyll").write_text("", encoding="utf-8")
    return rendered_site, postprocess_report


def validate_site(output_dir: Path) -> dict[str, Any]:
    """Validate links, fragments, and deployable resources in the site."""

    return validate_rendered_site(output_dir).as_dict()


def write_build_diagnostics(
    report_path: Path,
    validation: dict[str, Any],
    transformer: BookTransformer,
    glossary_warnings: list[str],
    postprocess_report: PostprocessReport,
) -> None:
    report = {
        "schema_version": 1,
        **validation,
        "used_terms": len(transformer.used_terms),
        "glossary_entries": transformer.glossary_entry_count,
        "glossary_keys": transformer.glossary_key_count,
        "missing_terms": sorted(transformer.missing_terms),
        "unresolved_references": sorted(transformer.unresolved_references),
        "glossary_warnings": glossary_warnings,
        "postprocess": postprocess_report.as_dict(),
        "toolchain": {
            "python": sys.version.split()[0],
            "pandoc": RUNNER.version(CONFIG.tools.pandoc),
            "quarto": RUNNER.version(str(QUARTO)),
            "xelatex": RUNNER.version(CONFIG.tools.xelatex),
            "dvisvgm": RUNNER.version(CONFIG.tools.dvisvgm),
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def mark_generated_site(
    rendered_site: Path,
    publication_dir: Path,
) -> None:
    """Mark a rendered site using the planned publication path as context."""

    (rendered_site / ".generated-site").write_text(
        "site-build-v1\n", encoding="utf-8"
    )
    write_site_fingerprint(
        PROJECT_ROOT,
        rendered_site,
        output_dir=publication_dir,
    )


def serve_site(output_dir: Path, port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(output_dir))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    log(f"预览地址：http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        log("预览服务器已停止")
    finally:
        server.server_close()


def build(arguments: argparse.Namespace) -> int:
    ensure_tool(CONFIG.tools.pandoc)
    if not MAIN_TEX.exists() or not SETTINGS_TEX.exists():
        fail("必须从项目根目录运行，且项目根目录需要 main.tex/settings.tex")

    output_dir = CONFIG.paths.resolve_output(arguments.output)

    computation_orders = load_computation_orders(CONFIG.paths)
    site_metadata = load_site_metadata(CONFIG.paths)
    chapter_progress = load_chapter_progress(CONFIG.paths)
    notation_catalog = load_notation_catalog(CONFIG.paths)

    log("读取术语和定理配置")
    (
        glossary,
        terms_by_directory,
        conflicting_term_keys,
        glossary_warnings,
        glossary_catalog,
    ) = load_glossary(CONFIG.paths)
    theorem_specs = parse_theorem_specs(CONFIG.paths)
    for warning in glossary_warnings:
        print(f"[web] 警告：{warning}", file=sys.stderr)
    log(
        f"发现 {len(glossary_catalog)} 条 NewTerm、"
        f"{len(glossary)} 个唯一术语键、"
        f"{len(theorem_specs)} 类定理环境"
    )

    latex_tables = stage_sources(
        theorem_specs,
        glossary,
        terms_by_directory,
        conflicting_term_keys,
        config=CONFIG,
        runner=RUNNER,
    )
    log("Pandoc 正在解析完整 LaTeX 文档")
    document = parse_latex_to_ast(CONFIG, RUNNER)

    transformer = BookTransformer(
        theorem_specs,
        glossary,
        glossary_catalog,
        latex_tables,
        project_root=PROJECT_ROOT,
    )
    document = transformer.transform(document)

    log("使用 Quarto Book 生成多页面 HTML")
    rendered_site, postprocess_report = write_quarto_site(
        document,
        transformer,
        computation_orders,
        site_metadata,
        chapter_progress,
        notation_catalog,
    )
    validation = validate_site(rendered_site)
    write_build_diagnostics(
        CONFIG.paths.build_dir / "diagnostics.json",
        validation,
        transformer,
        glossary_warnings,
        postprocess_report,
    )
    mark_generated_site(rendered_site, output_dir)

    if transformer.missing_terms:
        print(
            "[web] 未找到定义的术语："
            + ", ".join(sorted(transformer.missing_terms)),
            file=sys.stderr,
        )
    if transformer.unresolved_references:
        print(
            "[web] 未解析的交叉引用："
            + ", ".join(sorted(transformer.unresolved_references)),
            file=sys.stderr,
        )

    validation_errors = bool(
        validation["broken_links"]
        or validation["broken_resources"]
        or validation["duplicate_ids"]
        or validation["duplicate_resource_ids"]
    )
    if validation_errors and CONFIG.policy.strict_broken_resources:
        fail(
            "站点发布校验失败："
            f"失效链接 {len(validation['broken_links'])} 个，"
            f"失效资源 {len(validation['broken_resources'])} 个，"
            f"含重复内容 ID 的页面 {len(validation['duplicate_ids'])} 个；"
            "含重复资源 ID 的页面 "
            f"{len(validation['duplicate_resource_ids'])} 个；"
            "旧站点未被替换"
        )
    if arguments.strict and (
        transformer.missing_terms
        or transformer.unresolved_references
        or validation_errors
    ):
        log("严格校验未通过；旧站点未被替换")
        return 2

    cleanup_warnings = atomic_publish_directory(
        rendered_site,
        output_dir,
        html_dir=HTML_DIR,
        protected=(CONFIG.paths.build_dir,),
    )
    for warning in cleanup_warnings:
        RUNNER.warning(warning)
    log(
        f"完成：{output_dir.relative_to(PROJECT_ROOT)} "
        f"（{validation['html_pages']} 个页面，"
        f"使用术语 {len(transformer.used_terms)} 个，"
        f"术语表 {transformer.glossary_entry_count} 条，"
        f"失效链接 {len(validation['broken_links'])} 个）"
    )
    if arguments.serve:
        serve_site(output_dir, arguments.port)
    return 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 main.tex 转换成保留章节与数学环境的多页面 HTML"
    )
    parser.add_argument(
        "--output",
        default=CONFIG.paths.default_output_dir.relative_to(HTML_DIR).as_posix(),
        help=(
            "html/ 内的输出目录，默认 "
            + CONFIG.paths.default_output_dir.relative_to(HTML_DIR).as_posix()
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="存在未定义术语、未解析引用或发布校验错误时返回失败",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="构建完成后启动本地预览服务器",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="本地预览端口，默认 8000",
    )
    return parser.parse_args()


def main() -> int:
    try:
        return build(parse_arguments())
    except BuildError as error:
        print(f"[web] 错误：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
