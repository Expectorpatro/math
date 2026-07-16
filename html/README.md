# LaTeX 教材网页构建

这里的构建过程不会修改项目中的任何 `.tex` 文件。`main.tex` 仍是唯一正文
来源；脚本只在 `html/.build/` 中创建临时副本、Pandoc AST 和临时 Quarto
章节。最终网页使用原生 Quarto Book 布局。

## 构建

在项目根目录执行：

```bash
python3 html/build.py
```

网页生成在 `html/site/`，每个 `chapter` 对应一个 Quarto Book 页面，左侧是
整本书的章节索引，页面右侧是当前章目录。

首页正文写在 `html/home.md`，可直接使用 Markdown 修改或补充。标题、作者、
邮箱和日期读取自 `settings.tex` 中的 `title/author/date`。

站点的首次发布日期、最近内容更新日期和 GitHub 仓库写在
`html/site-meta.json`；网站构建日期由构建当天自动生成。19 个正文章节的完成度
集中写在 `html/chapter-progress.json`：填写 `0`–`100` 的整数即可，`null`
表示尚未填写。构建会严格检查章节键，避免拼写错误被静默忽略。

符号规范的唯一来源是
`skills/textbook-latex-style/references/notation-catalog.json`。构建会据此生成
“符号与记号说明”页面，项目内的 `textbook-latex-style` skill 也读取同一文件，
因此网页说明与后续 Agent 的写作约定保持一致。

构建并启动本地预览：

```bash
python3 html/build.py --serve
```

然后访问 <http://127.0.0.1:8000/>。

不要直接双击 `site/index.html` 预览：浏览器在 `file://` 模式下会阻止
Quarto 读取 `search.json`，站内搜索因此无法工作。GitHub Pages 等 HTTP
部署不受此限制。

## 计算实验

计算实验由 Python/Jupyter 或 R/Quarto 在各自环境中独立运行。网页构建不会
执行分析代码，只读取已经渲染好的、自包含的 `result.html`，并按照章节旁边
`computations.order` 中规定的顺序追加到该 chapter 的末尾。

### 目录约定

每个数学模块把计算文档放在自身目录中。例如线性模型模块：

```text
statistics/Linear-model/
├── main.tex
├── computations.order
└── computations/
    └── 01-linear-regression/
        ├── python/              # 使用 Python 时创建
        │   ├── environment.yml  # Conda 环境定义，提交
        │   ├── analysis.ipynb
        │   └── result.html      # 执行并渲染后生成，需要提交
        └── r/                   # 使用 R 时创建
            ├── analysis.qmd
            ├── renv.lock        # 初始化后生成，提交
            ├── renv/            # 本地环境，不提交
            └── result.html      # 执行并渲染后生成，需要提交
```

`computations.order` 使用普通 Markdown，不需要 JSON 或其他清单格式：

```markdown
# 线性模型计算实验

## 线性回归：Python 与 R 对照

- computations/01-linear-regression/python/result.html
- computations/01-linear-regression/r/result.html
```

每个二级标题表示一个计算实验，标题出现的顺序决定网页编号；每个实验可以只列
一个 Python 结果、只列一个 R 结果，也可以同时列出两个结果。上面的例子会生成
“实验 01”，其中先显示 Python Notebook，再显示 R Quarto 文档。如果实验只
适合一种语言，就只保留对应的一行路径。

### Python/Jupyter 环境（Conda）

在 Python 案例目录创建并激活 Conda 环境：

```bash
cd statistics/Linear-model/computations/01-linear-regression/python
conda env create -f environment.yml
conda activate textbook-linear-regression
jupyter lab analysis.ipynb
```

`environment.yml` 是项目需要提交的 Conda 环境定义；`conda env create` 会读取它，
创建其中 `name` 指定的环境。已有同名环境时不需要重复创建。

在 Jupyter 中执行 `Run All` 并保存 Notebook，然后使用同一个已激活环境渲染
自包含 HTML：

```bash
quarto render analysis.ipynb --to html --output result.html \
  -M embed-resources:true
```

### R/Quarto 环境

在 R 案例目录使用独立的 `renv` 环境：

```bash
cd statistics/Linear-model/computations/01-linear-regression/r
R
```

在 R 中初始化并记录依赖：

```r
install.packages("renv")
renv::init()
renv::install(c("dplyr", "ggplot2", "broom"))
renv::snapshot()
```

退出 R 后渲染文档：

```bash
quarto render analysis.qmd --to html --output result.html
```

`analysis.qmd` 已设置 `embed-resources: true`，因此文字、代码、表格、公式和
图片都会包含在单个 `result.html` 中。

### 插入教材网页

结果文件生成后，回到项目根目录执行：

```bash
python3 html/build.py
```

`build.py` 会：

- 查找与各章 `main.tex` 同目录的 `computations.order`；
- 根据二级标题和列表顺序生成案例编号；
- 提取每个 `result.html` 的正文，处理重复锚点与标题层级；
- 将结果追加到对应 chapter 的最后；
- 在 Quarto 渲染完成后插入最终 chapter HTML，保留原始公式、表格和图片；
- 为 Python/Jupyter 和 R/Quarto 增加统一的语言标签和教材样式；
- 在结果缺失或仍引用外部图片时给出明确错误并停止构建。

提交和发布时，应提交 Notebook、QMD、`computations.order`、生成的
`result.html`、Conda 的 `environment.yml` 和更新后的 `html/site/`；不要提交 `renv/`、
`.quarto/` 或 Notebook 缓存。GitHub Pages 仍然只发布 `html/site/`，因此每次
修改计算案例后都要先重新渲染结果，再执行网页构建。

## 发布到 GitHub Pages

项目使用 `.github/workflows/pages.yml` 发布已经在本地生成的
`html/site/`。GitHub Actions 不会重新运行 Quarto，因此每次修改 `.tex`
文件后，应先在本地构建，再提交和推送。

需要提交到 GitHub 的内容包括：

- 原始 LaTeX 文件和正文引用的图片、代码等资源；
- `html/build.py`、`html/home.md`、`html/style.css`、`html/textbook-ui.js`
  与 `html/favicon.svg`；
- `html/site-meta.json`、`html/chapter-progress.json`，以及
  `skills/textbook-latex-style/` 中由网页和 Agent 共同使用的符号规范；
- 完整的 `html/site/`，包括 `index.html`、`chapters/`、`site_libs/`、
  `search.json` 和样式文件；
- `.github/workflows/pages.yml`。

`html/.build/`、LaTeX 编译临时文件和 `.DS_Store` 不需要提交，已经由
`.gitignore` 排除。根目录 `.gitignore` 对 `html/site/` 中的 HTML 文件
设置了例外，因此构建结果可以正常进入 Git。

### 第一次启用

先把项目推送到 GitHub：

```bash
python3 html/build.py
git add -A
git status
git commit -m "github.pages"
git push origin main
```

提交前检查 `git status`，其中应能看到 `html/site/index.html` 和
`html/site/chapters/` 下的网页文件；如果看不到，不要提交，先检查
`.gitignore`。

随后打开 GitHub 仓库的 `Settings` → `Pages`，在
`Build and deployment` 中将 `Source` 设置为 `GitHub Actions`。推送到
`main` 后，可以在仓库的 `Actions` 页面查看部署进度，也可以在该页面手动
运行 `Deploy textbook to GitHub Pages` 工作流。

当前仓库的网页地址预计为：

<https://expectopatro.github.io/math/>

### 日常更新

以后每次修改原始教材，只需在项目根目录执行：

```bash
python3 html/build.py
git add -A
git status
git commit -m "更新教材网页"
git push origin main
```

推送到 `main` 后，GitHub Actions 会自动用最新的 `html/site/` 覆盖线上
版本。首页显示的编译日期是执行 `build.py` 时生成的日期。

如果本次修改涉及计算实验，应先在对应的 Python 或 R 环境中生成最新的
`result.html`，再执行上述日常更新流程。

## 当前转换规则

- `part/chapter/section/subsection/subsubsection` 保留为对应网页层级。
- 暂存时自动启用 `main.tex` 中被注释的 `part` 和章节 `include`，但不修改
  原始 `main.tex`。
- `newtheorem` 声明会从 `settings.tex` 读取，定理环境按原父计数器编号。
- `proof` 保留为独立证明块，默认展开并允许逐个或整页折叠；折叠状态在当前
  浏览会话中保留，打印时始终显示证明正文。
- `label/ref/eqref/cref` 转换为网页内或跨页面链接。点击 `cref` 后来源链接会
  显示已访问状态，目标短暂高亮；紧随引用的 `(2)`、`(5.b)(5.c)` 等条目提示会
  纳入整条链接，并在跳转后说明应查看的具体项目。
- 浏览器后退或前进时会按最近标题与相对偏移恢复阅读位置。
- `equation/align/gather` 保留为 MathJax 数学环境。
- `enumerate/itemize` 中的显示公式会保留对应列表层级，公式后续条目不会被
  误判为代码块。
- 所有 `english.tex` 中的 `NewTerm` 都会进入术语表；总览提供 A–Z 导航，
  每个字母独立成页并按英文名称排序。
- 每条术语都建立独立搜索记录，搜索结果可直接跳到对应条目；重复索引键的
  不同定义会分别保留并显示来源。
- 左侧目录只显示“中英术语表”；A–Z 字母页通过总览卡片、前后导航和搜索
  访问，不占用侧栏长度。
- `gls{Key}` 按“中文（English）”显示，并链接到中英术语表。
- `qedhere` 交由网页证明块统一显示结尾方块，不再传给 MathJax。
- `algorithm` 与 `algpseudocode` 会转换为带标题、章内编号、行号和缩进的
  算法块；支持 `Require/Ensure/State/Statex`、条件、循环、函数、注释、
  `Call/Return` 以及 `label/cref` 算法引用。
- 行内数学公式通过 CSS 在左右各保留少量视觉间距，不修改原始 TeX 中的
  `$...$`。
- `minted` 和 `inputminted` 由 Pandoc 转成带语法高亮的代码块；后者引用的
  代码文件会自动复制到暂存目录。
- `densityplot` 环境在 PDF 中保留固定参数的 TikZ/PGFPlots 图，在网页中替换为
  可调整参数的 SVG 密度曲线；支持 PDF/CDF 切换、PDF 区间概率、坐标缩放和
  曲线对比。鼠标移入曲线区域时会显示当前位置与函数值；图表滚动到视口附近
  才加载数值计算、探针和绘图脚本。相关逻辑按加载器、数学计算、鼠标探针与
  图表界面拆分，脚本随静态站点一同发布，不依赖外部服务。
- 每个行间公式会保留转换前的原始 LaTeX；网页在公式右上角提供复制按钮，
  复制结果不会包含网页构建时生成的编号标签。
- 与章节同目录的 `computations.order` 控制 Jupyter/Quarto 结果的顺序，
  构建时自动编号并追加到相应 chapter 末尾。
- 右侧当前章目录会随正文滚动自动高亮，并保持当前条目可见。
- 每个正文页提供“在 GitHub 上报告本页问题”入口；首页和项目状态页提供源代码、
  错误报告、内容建议与提交记录入口。
- 项目状态页自动汇总章节进度、定理类环境、证明、算法、行间公式、交互图和术语
  数量，不需要手工维护统计数字。

构建时使用 `--strict`，可以让未定义术语或未解析引用导致构建失败：

```bash
python3 html/build.py --strict
```

## 目录

- `build.py`：唯一构建入口。
- `style.css`：网页样式。
- `textbook-ui.js`：主题、证明折叠、阅读位置、交叉引用提示与页面反馈入口。
- `site-meta.json`：发布日期、内容更新日期和 GitHub 仓库。
- `chapter-progress.json`：19 个正文章节的完成百分比。
- `.build/`：Pandoc AST、临时 `.qmd` 和 Quarto 工程，每次构建时更新。
- `site/`：最终静态网站，可发布到 GitHub Pages。
- `site/build-report.json`：未定义术语、未解析引用和失效链接报告。
- `computations.order`：某一数学章节的计算实验标题与结果显示顺序。
- `.github/workflows/pages.yml`：从项目根目录发布 `html/site/` 的 GitHub
  Pages 工作流。

默认调用 Positron 内置的 Quarto：

```text
/Applications/Positron.app/Contents/Resources/app/quarto/bin/quarto
```

如需使用其他版本，可以设置 `QUARTO` 环境变量。

## GitHub 语言统计

根目录 `.gitattributes` 将所有 `.html` 标记为不参与语言识别，并额外将生成站点与
计算结果标记为生成文件。该设置必须提交到默认分支后 GitHub Linguist 才会采用；
仓库语言条可能存在短暂缓存，但以后构建产生的 HTML 不会再把项目识别为 HTML
项目。此规则只影响 GitHub 的语言统计，不影响 GitHub Pages 发布这些文件。
