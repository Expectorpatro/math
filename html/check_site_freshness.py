#!/usr/bin/env python3
"""Refuse deployment when committed HTML does not match current sources."""

from __future__ import annotations

from pathlib import Path
import sys


HTML_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = HTML_DIR.parent
sys.path.insert(0, str(HTML_DIR))

from site_builder.errors import BuildError
from site_builder.config import BuildConfig
from site_builder.freshness import verify_site_fingerprint


def main() -> int:
    try:
        config = BuildConfig.load(HTML_DIR)
        workflow_output = (HTML_DIR / "site").resolve()
        if config.paths.default_output_dir != workflow_output:
            raise BuildError(
                "Pages 工作流当前发布 html/site，但 build-config.toml "
                "配置了其他输出目录；请同步更新 .github/workflows/pages.yml"
            )
        verify_site_fingerprint(
            PROJECT_ROOT,
            config.paths.default_output_dir,
        )
    except BuildError as error:
        print(f"[web] 错误：{error}", file=sys.stderr)
        return 1
    print("[web] 已确认提交的 HTML 与当前源码一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
