"""Generate the home, status, notation, and Quarto project pages."""

from __future__ import annotations

from datetime import date as calendar_date
import html
import re
from typing import Any
from urllib.parse import urlencode

from .errors import BuildError
from .metadata import book_contact_email, quarto_date, recent_git_commits, yaml_quote
from .models import QuartoPage
from .pages import page_title
from .pandoc_transform import BookTransformer, ast_plain_text, node_identifier
from .quarto import QuartoProjectWriter
from .runtime import CONFIG

HTML_DIR = CONFIG.paths.html_dir
HOME_CONTENT = HTML_DIR / "home.md"
QUARTO_PROJECT_DIR = CONFIG.paths.quarto_project_dir
QUARTO_WRITER = QuartoProjectWriter(CONFIG)
SITE_DESCRIPTION = (
    "持续整理的在线数学教材，涵盖代数、分析、概率、优化与统计，"
    "强调逻辑自洽、证明完整与持续维护。"
)


def fail(message: str) -> None:
    raise BuildError(message)


def github_issue_url(
    metadata: dict[str, str],
    *,
    title: str,
    body: str,
    labels: str = "",
) -> str:
    query: dict[str, str] = {"title": title, "body": body}
    if labels:
        query["labels"] = labels
    return f"{metadata['github_url']}/issues/new?{urlencode(query)}"


def render_site_timeline(metadata: dict[str, str]) -> str:
    return (
        '<dl class="site-timeline" aria-label="项目时间线">'
        '<div><dt>首次发布</dt>'
        f'<dd><time datetime="{metadata["first_published"]}">'
        f'{metadata["first_published"]}</time></dd></div>'
        '<div><dt>最近内容更新</dt>'
        f'<dd><time datetime="{metadata["content_updated"]}">'
        f'{metadata["content_updated"]}</time></dd></div>'
        '<div><dt>网站构建</dt>'
        f'<dd><time datetime="{calendar_date.today().isoformat()}">'
        f'{calendar_date.today().isoformat()}</time></dd></div></dl>'
    )


def render_recent_commits(
    metadata: dict[str, str], commits: list[dict[str, str]]
) -> str:
    if commits:
        items = "".join(
            '<li><a href="'
            + metadata["github_url"]
            + "/commit/"
            + html.escape(commit["hash"], quote=True)
            + '"><code>'
            + html.escape(commit["short_hash"])
            + "</code><span>"
            + html.escape(commit["subject"])
            + "</span><time datetime=\""
            + html.escape(commit["date"], quote=True)
            + '\">'
            + html.escape(commit["date"])
            + "</time></a></li>"
            for commit in commits
        )
    else:
        items = '<li class="home-commit-empty">当前构建无法读取本地提交记录。</li>'
    return (
        '<div class="home-update-heading"><span class="home-live-badge">'
        '<i aria-hidden="true"></i>持续更新中</span>'
        f'<a href="{metadata["github_url"]}/commits/main/">查看全部提交</a></div>'
        f'<ol class="home-commits">{items}</ol>'
    )


def render_github_actions(metadata: dict[str, str]) -> str:
    error_url = github_issue_url(
        metadata,
        title="[错误报告] ",
        body="请描述发现的问题，并附上相关页面地址或章节位置。\n\n问题描述：\n\n页面地址：",
        labels="bug",
    )
    suggestion_url = github_issue_url(
        metadata,
        title="[内容建议] ",
        body="请说明建议修改或补充的内容，并附上相关章节位置。\n\n建议内容：\n\n相关章节：",
        labels="content",
    )
    actions = [
        ("bi-code-slash", "查看源代码", metadata["github_url"]),
        ("bi-bug", "报告错误", error_url),
        ("bi-chat-left-text", "提出内容建议", suggestion_url),
        ("bi-clock-history", "查看更新记录", f'{metadata["github_url"]}/commits/main/'),
    ]
    return '<nav class="github-actions" aria-label="GitHub 项目入口">' + "".join(
        f'<a href="{html.escape(url, quote=True)}"><i class="bi {icon}" '
        f'aria-hidden="true"></i><span>{label}</span>'
        '<i class="bi bi-arrow-up-right" aria-hidden="true"></i></a>'
        for icon, label, url in actions
    ) + "</nav>"


def project_statistics(
    transformer: BookTransformer,
    pages: list[QuartoPage],
) -> list[tuple[str, int, str]]:
    chapter_count = sum(
        page.part not in {None, "中英术语表"} for page in pages
    )
    counts = transformer.environment_counts
    return [
        ("正文章节", chapter_count, "chapter"),
        ("定义", counts.get("definition", 0), "definition"),
        ("定理", counts.get("theorem", 0), "theorem"),
        ("性质", counts.get("property", 0), "property"),
        ("引理", counts.get("lemma", 0), "lemma"),
        ("推论", counts.get("corollary", 0), "corollary"),
        ("证明", transformer.proof_count, "proof"),
        ("算法", transformer.content_counts.get("algorithm", 0), "algorithm"),
        ("行间公式", transformer.content_counts.get("display-math", 0), "equation"),
        ("交互图", transformer.content_counts.get("interactive-density-plot", 0), "plot"),
        ("中英术语", transformer.glossary_entry_count, "glossary"),
    ]


def render_project_snapshot(statistics: list[tuple[str, int, str]]) -> str:
    featured = [
        item
        for item in statistics
        if item[2] in {"definition", "theorem", "property", "proof"}
    ]
    return '<div class="project-snapshot">' + "".join(
        f'<div><strong>{value}</strong><span>{html.escape(label)}</span></div>'
        for label, value, _key in featured
    ) + '</div><a class="home-section-link" href="project-status.html">查看完整项目状态 <span aria-hidden="true">→</span></a>'


def render_statistics_grid(statistics: list[tuple[str, int, str]]) -> str:
    return '<div class="statistics-grid">' + "".join(
        f'<article class="statistic-card statistic-card--{key}">'
        f'<span>{html.escape(label)}</span><strong>{value}</strong></article>'
        for label, value, key in statistics
    ) + "</div>"


def render_progress_overview(
    pages: list[QuartoPage],
    progress: dict[str, int | None],
) -> str:
    groups: list[tuple[str, list[QuartoPage]]] = []
    group_lookup: dict[str, list[QuartoPage]] = {}
    displayed_progress = {
        key: value for key, value in progress.items() if key != "inequalities"
    }
    for page in pages:
        slug = page.source_path.stem
        if slug not in displayed_progress or page.part is None:
            continue
        part = page.part or "其他"
        if part not in group_lookup:
            group_lookup[part] = []
            groups.append((part, group_lookup[part]))
        group_lookup[part].append(page)
    sections: list[str] = []
    for part, group_pages in groups:
        rows: list[str] = []
        for page in group_pages:
            slug = page.source_path.stem
            value = displayed_progress[slug]
            label = "待填写" if value is None else f"{value}%"
            width = 0 if value is None else value
            state = " status-progress-row--unset" if value is None else ""
            title = re.sub(r"^第\s*\d+\s*章\s*", "", page_title(page)).strip()
            rows.append(
                f'<a class="status-progress-row{state}" '
                f'href="{page.source_path.with_suffix(".html").as_posix()}">'
                f'<span class="status-progress-row__title">{html.escape(title)}</span>'
                '<span class="status-progress-row__track" aria-hidden="true">'
                f'<i style="--chapter-progress: {width}%"></i></span>'
                f'<strong>{label}</strong></a>'
            )
        display_part = re.sub(
            r"^第\s*\d+\s*部分\s*", "", part
        ).strip()
        sections.append(
            f'<section class="status-part"><h2>{html.escape(display_part)}</h2>'
            + "".join(rows)
            + "</section>"
        )
    values = [
        value for value in displayed_progress.values() if value is not None
    ]
    average = round(sum(values) / len(values)) if values else None
    summary = (
        f"已填写 {len(values)} / {len(displayed_progress)} 章"
        + (f"，已填写章节平均完成度 {average}%" if average is not None else "")
    )
    return (
        f'<p class="status-progress-summary">{summary}</p>'
        '<div class="status-progress-groups">'
        + "".join(sections)
        + "</div>"
    )


def write_project_status_page(
    *,
    metadata: dict[str, str],
    commits: list[dict[str, str]],
    pages: list[QuartoPage],
    progress: dict[str, int | None],
    statistics: list[tuple[str, int, str]],
) -> None:
    content = "\n".join(
        [
            "---",
            "title: 项目状态",
            f"description: {yaml_quote('笔记维护时间、章节完成度与内容统计。')}",
            "---",
            "",
            ':::: {.project-status-page}',
            '::: {.status-section}',
            '<p class="status-kicker">MAINTENANCE</p>',
            "## 维护时间",
            "",
            render_site_timeline(metadata),
            render_recent_commits(metadata, commits),
            "",
            ":::",
            "",
            '::: {.status-section}',
            '<p class="status-kicker">PROGRESS</p>',
            "## 章节完成度",
            "",
            render_progress_overview(pages, progress),
            "",
            ":::",
            "",
            '::: {.status-section}',
            '<p class="status-kicker">CONTENT</p>',
            "## 笔记数据",
            "",
            render_statistics_grid(statistics),
            "",
            ":::",
            "",
            '::: {.status-section}',
            '<p class="status-kicker">CONTRIBUTE</p>',
            "## 参与维护",
            "",
            render_github_actions(metadata),
            "",
            ":::",
            "",
            "::::",
            "",
        ]
    )
    (QUARTO_PROJECT_DIR / "project-status.qmd").write_text(
        content, encoding="utf-8"
    )


def write_notation_page(catalog: dict[str, Any]) -> None:
    def raw_html_text(value: Any) -> str:
        """Escape text that Pandoc will encounter inside a raw HTML table.

        Pandoc still interprets Markdown punctuation in raw table cells.  Emit
        ASCII punctuation as numeric HTML entities so TeX operators, scripts,
        delimiters and literal code survive unchanged.  The browser decodes
        the entities before MathJax inspects the DOM.
        """
        return "".join(
            character
            if character.isalnum()
            or character.isspace()
            or ord(character) >= 128
            else f"&#{ord(character)};"
            for character in str(value)
        )

    entries = catalog["entries"]
    category_order = catalog.get("category_order", [])
    categories = list(category_order)
    categories.extend(
        category
        for category in dict.fromkeys(entry["category"] for entry in entries)
        if category not in categories
    )
    sections: list[str] = []
    for category in categories:
        rows: list[str] = []
        for entry in entries:
            if entry["category"] != category:
                continue
            source = raw_html_text(entry["symbol"])
            rendered = raw_html_text(entry.get("render_tex", entry["symbol"]))
            rows.append(
                f'<tr id="notation-{html.escape(entry["id"], quote=True)}">'
                f'<td class="notation-rendered">&#92;({rendered}&#92;)</td>'
                f'<td class="notation-source"><code>{source}</code></td>'
                f'<td class="notation-meaning"><strong>{raw_html_text(entry["name"])}</strong>'
                f'<p>{raw_html_text(entry["meaning"])}</p></td>'
                f'<td class="notation-scope">{raw_html_text("、".join(entry["scope"]))}</td>'
                '</tr>'
            )
        if rows:
            sections.append(
                f'## {category} {{.notation-section-title}}\n\n'
                '<table class="notation-table">'
                '<thead><tr><th>数学记号</th><th>LaTeX</th><th>含义</th><th>适用范围</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table>\n'
            )
    content = "\n".join(
        [
            "---",
            "title: 符号与记号说明",
            f"description: {yaml_quote('本书常用数学符号索引。')}",
            "---",
            "",
            '[$0$]{.notation-math-bootstrap aria-hidden="true"}',
            "",
            *sections,
            "",
        ]
    )
    (QUARTO_PROJECT_DIR / "notation.qmd").write_text(content, encoding="utf-8")


def write_quarto_config(
    document: dict[str, Any],
    pages: list[QuartoPage],
    transformer: BookTransformer,
    site_metadata: dict[str, str],
    chapter_progress: dict[str, int | None],
    notation_catalog: dict[str, Any],
) -> None:
    title = ast_plain_text(document["meta"].get("title", {})).strip()
    author = ast_plain_text(document["meta"].get("author", {})).strip()
    raw_date = ast_plain_text(document["meta"].get("date", {})).strip()
    date = quarto_date(raw_date)
    email = book_contact_email()
    title = title or "数学教材"
    commits = recent_git_commits()
    statistics = project_statistics(transformer, pages)
    write_project_status_page(
        metadata=site_metadata,
        commits=commits,
        pages=pages,
        progress=chapter_progress,
        statistics=statistics,
    )
    write_notation_page(notation_catalog)
    preface_href = next(
        (
            page.source_path.with_suffix(".html").as_posix()
            for page in pages
            if re.sub(r"^第\s*\d+\s*章\s*", "", page_title(page)).strip()
            == "前言"
        ),
        "chapters/preface.html",
    )
    glossary_href = next(
        (
            page.source_path.with_suffix(".html").as_posix()
            for page in pages
            if page.blocks and node_identifier(page.blocks[0]) == "glossary"
        ),
        "chapters/glossary.html",
    )
    chapter_count = sum(
        page.part not in {None, "中英术语表"} for page in pages
    )
    knowledge_parts: list[str] = []
    for page in pages:
        if page.part is None:
            continue
        part_title = re.sub(
            r"^第\s*\d+\s*部分\s*", "", page.part
        ).strip()
        if (
            part_title in {"中英术语表", "不等式"}
            or part_title in knowledge_parts
        ):
            continue
        knowledge_parts.append(part_title)

    index = [
        "---",
        f"title: {yaml_quote(title)}",
        f"description: {yaml_quote(SITE_DESCRIPTION)}",
    ]
    if author:
        if email:
            index.extend(
                [
                    "author:",
                    f"  - name: {yaml_quote(author)}",
                    f"    email: {yaml_quote(email)}",
                ]
            )
        else:
            index.append(f"author: {yaml_quote(author)}")
    if date:
        index.append(f"date: {yaml_quote(date)}")
        index.append("date-format: long")
    index.append(
        f"date-modified: {yaml_quote(calendar_date.today().isoformat())}"
    )
    home_content = (
        HOME_CONTENT.read_text(encoding="utf-8").strip()
        if HOME_CONTENT.exists()
        else "这是由项目中的 `main.tex` 自动生成的在线版本。"
    )
    home_content = (
        home_content.replace("__BOOK_EMAIL__", html.escape(email, quote=True))
        .replace("__BUILD_DATE__", calendar_date.today().isoformat())
        .replace("__BUILD_YEAR__", str(calendar_date.today().year))
        .replace("__PREFACE_HREF__", preface_href)
        .replace("__GLOSSARY_HREF__", glossary_href)
        .replace("__CHAPTER_COUNT__", str(chapter_count))
        .replace("__PART_COUNT__", str(len(knowledge_parts)))
        .replace("__SITE_TIMELINE__", render_site_timeline(site_metadata))
        .replace("__RECENT_COMMITS__", render_recent_commits(site_metadata, commits))
        .replace("__GITHUB_ACTIONS__", render_github_actions(site_metadata))
        .replace("__PROJECT_SNAPSHOT__", render_project_snapshot(statistics))
    )
    remaining_placeholders = sorted(set(re.findall(r"__[A-Z][A-Z_]+__", home_content)))
    if remaining_placeholders:
        fail("首页存在未替换占位符：" + "、".join(remaining_placeholders))
    index.extend(
        [
            "---",
            "",
            home_content,
        ]
    )
    if email and "textbook-home" not in home_content:
        index.extend(
            [
                "",
                f"联系邮箱：[{email}](mailto:{email})",
            ]
        )
    index.append("")
    (QUARTO_PROJECT_DIR / "index.qmd").write_text(
        "\n".join(index),
        encoding="utf-8",
    )

    QUARTO_WRITER.write_sidebar_rules(pages)
    QUARTO_WRITER.write_config(
        pages=pages,
        title=title,
        author=author,
        email=email,
        publication_date=date,
        description=SITE_DESCRIPTION,
        site_url=site_metadata["site_url"],
        repository_url=site_metadata["github_url"],
    )
