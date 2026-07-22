"""Load and validate checked-in metadata used by generated pages."""

from __future__ import annotations

from datetime import date as calendar_date
import json
import re
import subprocess
from typing import Any

from .errors import BuildError
from .latex_sources import strip_tex_comments
from .runtime import CONFIG

PROJECT_ROOT = CONFIG.paths.project_root
HTML_DIR = CONFIG.paths.html_dir
SETTINGS_TEX = CONFIG.paths.settings_tex
SITE_META = HTML_DIR / "site-meta.json"
CHAPTER_PROGRESS = HTML_DIR / "chapter-progress.json"
NOTATION_CATALOG = HTML_DIR / "notation-catalog.json"


def fail(message: str) -> None:
    raise BuildError(message)


def yaml_quote(value: str) -> str:
    return json.dumps(" ".join(value.split()), ensure_ascii=False)


def book_contact_email() -> str:
    text = strip_tex_comments(SETTINGS_TEX.read_text(encoding="utf-8"))
    match = re.search(
        r"\bEmail\s*:\s*"
        r"([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else ""


def quarto_date(value: str) -> str:
    normalized = " ".join(value.split())
    chinese = re.fullmatch(
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        normalized,
    )
    if chinese:
        year, month, day = map(int, chinese.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        return normalized
    return ""


def load_site_metadata() -> dict[str, str]:
    if not SITE_META.is_file():
        fail(f"缺少站点元数据：{SITE_META.relative_to(PROJECT_ROOT)}")
    try:
        metadata = json.loads(SITE_META.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"站点元数据不是有效 JSON：{error}")
    required = ("first_published", "content_updated", "repository")
    for key in required:
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            fail(f"site-meta.json 缺少字符串字段 {key!r}")
    for key in ("first_published", "content_updated"):
        try:
            calendar_date.fromisoformat(metadata[key])
        except ValueError:
            fail(f"site-meta.json 的 {key} 必须使用 YYYY-MM-DD")
    repository = metadata["repository"].strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        fail("site-meta.json 的 repository 必须写成 owner/repository")
    owner, repository_name = repository.split("/", 1)
    metadata["repository"] = repository
    metadata["github_url"] = f"https://github.com/{repository}"
    metadata["site_url"] = (
        f"https://{owner.lower()}.github.io/{repository_name}/"
    )
    return metadata


def load_chapter_progress() -> dict[str, int | None]:
    if not CHAPTER_PROGRESS.is_file():
        fail(f"缺少章节进度文件：{CHAPTER_PROGRESS.relative_to(PROJECT_ROOT)}")
    try:
        progress = json.loads(CHAPTER_PROGRESS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"章节进度文件不是有效 JSON：{error}")
    if not isinstance(progress, dict):
        fail("chapter-progress.json 顶层必须是对象")
    result: dict[str, int | None] = {}
    for key, value in progress.items():
        if not isinstance(key, str):
            fail("chapter-progress.json 的章节键必须是字符串")
        if value is not None and (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 100
        ):
            fail(f"章节 {key!r} 的完成度必须是 0–100 的整数或 null")
        result[key] = value
    return result


def load_notation_catalog() -> dict[str, Any]:
    if not NOTATION_CATALOG.is_file():
        fail(
            "缺少 notation 规范："
            f"{NOTATION_CATALOG.relative_to(PROJECT_ROOT)}"
        )
    try:
        catalog = json.loads(NOTATION_CATALOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"notation catalog 不是有效 JSON：{error}")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("notation-catalog.json 必须包含非空 entries 列表")
    required = ("symbol", "name", "meaning", "category", "scope")
    seen_symbols: set[tuple[str, str]] = set()
    seen_identifiers: set[str] = set()
    for list_key in ("principles", "category_order"):
        value = catalog.get(list_key, [])
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            fail(f"notation-catalog.json 的 {list_key} 必须是字符串列表")
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            fail(f"notation entry {index} 必须是对象")
        for key in required:
            if key == "scope":
                if (
                    not isinstance(entry.get(key), list)
                    or not entry[key]
                    or not all(
                        isinstance(item, str) and item.strip()
                        for item in entry[key]
                    )
                ):
                    fail(f"notation entry {index} 的 scope 必须是非空列表")
            elif not isinstance(entry.get(key), str) or not entry[key].strip():
                fail(f"notation entry {index} 缺少字符串字段 {key!r}")
        identity = (entry["category"], entry["symbol"])
        if identity in seen_symbols:
            fail(f"notation catalog 重复条目：{identity}")
        seen_symbols.add(identity)
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[a-z][a-z0-9-]*", identifier
        ):
            fail(f"notation entry {index} 缺少稳定的 id（小写字母、数字、连字符）")
        if identifier in seen_identifiers:
            fail(f"notation catalog 重复 id：{identifier}")
        seen_identifiers.add(identifier)
        convention = entry.get("convention", "")
        if convention and not isinstance(convention, str):
            fail(f"notation entry {index} 的 convention 必须是字符串")
        render_tex = entry.get("render_tex", "")
        if render_tex and not isinstance(render_tex, str):
            fail(f"notation entry {index} 的 render_tex 必须是字符串")
        for list_key in ("avoid", "sources"):
            value = entry.get(list_key, [])
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                fail(f"notation entry {index} 的 {list_key} 必须是字符串列表")
    return catalog


def recent_git_commits(limit: int = 3) -> list[dict[str, str]]:
    result = subprocess.run(
        [
            "git",
            "log",
            f"-{limit}",
            "--date=short",
            "--format=%H%x1f%h%x1f%ad%x1f%s",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    commits: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split("\x1f", 3)
        if len(fields) != 4:
            continue
        full_hash, short_hash, commit_date, subject = fields
        commits.append(
            {
                "hash": full_hash,
                "short_hash": short_hash,
                "date": commit_date,
                "subject": subject,
            }
        )
    return commits
