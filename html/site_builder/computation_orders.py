"""Discover and validate the ordered computation-result manifest."""

from __future__ import annotations

from pathlib import Path
import re

from .config import BuildPaths
from .errors import BuildError
from .latex_sources import strip_tex_comments
from .models import ComputationGroup
from .pandoc_tables import latex_to_plain


def fail(message: str) -> None:
    raise BuildError(message)


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def load_computation_orders(
    paths: BuildPaths,
) -> dict[str, list[ComputationGroup]]:
    orders: dict[str, list[ComputationGroup]] = {}
    missing_results: list[Path] = []
    for order_path in sorted(paths.project_root.rglob("computations.order")):
        if is_inside(order_path, paths.html_dir):
            continue
        chapter_source = order_path.parent / "main.tex"
        if not chapter_source.is_file():
            fail(
                "computations.order 必须与包含 chapter 的 main.tex 放在同一目录："
                f"{order_path.relative_to(paths.project_root)}"
            )
        chapter_text = strip_tex_comments(
            chapter_source.read_text(encoding="utf-8")
        )
        chapter_match = re.search(
            r"\\chapter(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}",
            chapter_text,
        )
        if not chapter_match:
            fail(
                "找不到 computations.order 对应的 chapter："
                f"{chapter_source.relative_to(paths.project_root)}"
            )
        chapter_title = latex_to_plain(chapter_match.group(1)).strip()
        if chapter_title in orders:
            fail(f"章节 {chapter_title!r} 存在多个 computations.order")

        groups: list[ComputationGroup] = []
        current_title: str | None = None
        current_results: list[Path] = []

        def finish_group() -> None:
            nonlocal current_title, current_results
            if current_title is None:
                return
            if not current_results:
                fail(
                    f"计算案例 {current_title!r} 没有结果文件："
                    f"{order_path.relative_to(paths.project_root)}"
                )
            groups.append(
                ComputationGroup(
                    title=current_title,
                    result_paths=tuple(current_results),
                )
            )
            current_title = None
            current_results = []

        for line_number, raw_line in enumerate(
            order_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if not line or line.startswith("<!--"):
                continue
            if line.startswith("## "):
                finish_group()
                current_title = line[3:].strip()
                if not current_title:
                    fail(
                        f"空的计算案例标题：{order_path.relative_to(paths.project_root)}:"
                        f"{line_number}"
                    )
                continue
            if line.startswith("#"):
                continue
            if line.startswith("- "):
                if current_title is None:
                    fail(
                        f"结果路径必须位于二级标题之后："
                        f"{order_path.relative_to(paths.project_root)}:{line_number}"
                    )
                relative = Path(line[2:].strip())
                target = (order_path.parent / relative).resolve()
                if (
                    not is_inside(target, paths.project_root)
                    or target.suffix.lower() != ".html"
                ):
                    fail(
                        f"计算结果必须是项目内的 HTML 文件："
                        f"{order_path.relative_to(paths.project_root)}:{line_number}"
                    )
                current_results.append(target)
                if not target.is_file():
                    missing_results.append(target)
                continue
            fail(
                f"无法识别 computations.order 中的内容："
                f"{order_path.relative_to(paths.project_root)}:{line_number}"
            )
        finish_group()
        if not groups:
            fail(
                f"没有计算案例：{order_path.relative_to(paths.project_root)}"
            )
        orders[chapter_title] = groups

    if missing_results:
        details = "\n".join(
            f"  - {path.relative_to(paths.project_root)}"
            for path in missing_results
        )
        fail(
            "数值计算结果尚未生成。请先在各自的 Python/R 环境中渲染：\n"
            + details
        )
    return orders
