# LaTeX 教材网页构建

## 构建

在项目根目录执行：

```bash
python3 html/build.py
```

网页生成在 `html/site/`，每个 `chapter` 对应一个 Quarto Book 页面，左侧是整本书的章节索引，页面右侧是当前章目录。

首页正文写在 `html/home.md`，可直接使用 Markdown 修改或补充。标题、作者、邮箱和日期读取自 `settings.tex` 中的 `title/author/date`。

站点的首次发布日期、最近内容更新日期和 GitHub 仓库写在`html/site-meta.json`；网站构建日期由构建当天自动生成。19 个正文章节的完成度集中写在 `html/chapter-progress.json`：填写 `0`–`100` 的整数即可，`null`表示尚未填写。构建会严格检查章节键，避免拼写错误被静默忽略。

网页“符号与记号说明”页的构建数据位于 `html/notation-catalog.json`。该文件是网站源码的一部分，构建会据此生成页面。

构建并启动本地预览：

```bash
python3 html/build.py --serve
```

然后访问 <http://127.0.0.1:8000/>。

不要直接双击 `site/index.html` 预览：浏览器在 `file://` 模式下会阻止Quarto 读取 `search.json`，站内搜索因此无法工作。GitHub Pages 等 HTTP部署不受此限制。

## 自动测试

每次修改构建器、资源发布逻辑、HTML 后处理或页面交互代码后，应先在项目根目录运行：

```bash
python3 -m unittest discover -s html/tests -v
node --test html/tests/test_frontend_modules.js
```

测试只使用 Python 和 Node.js 自带的测试工具，不需要 Quarto、LaTeX、第三方测试框架或网络访问，临时文件只会写入被忽略的 `html/.build/tests/`。当前测试覆盖集中配置的合法性、发布目录保护与迁移、站点链接校验、图片与图题的 HTML 后处理、favicon 的统一引用、计算实验安全导入、主题切换，以及“只展开当前一级目录的二级目录”等关键行为。

通过自动测试后，再执行 `python3 html/build.py` 进行完整构建。失效链接、失效资源和重复 ID 默认就会阻止发布；如需进一步把未定义术语或未解析引用也视为失败，请使用：

```bash
python3 html/build.py --strict
```

## 计算实验

网页构建不会执行分析代码，只读取已经渲染好的、自包含的 `analysis.html`，并按照章节旁边 `computations.order` 中规定的顺序追加到对应 chapter 的末尾。

当前所有 R 计算实验共用**整个项目的一个 `renv` 环境**，不再为每个实验单独建立 `renv`。项目根目录的 `.Rprofile` 会激活`renv/activate.R`，根目录的 `renv.lock` 是全书 R 包版本的唯一锁文件。`environment/r/` 保留环境说明；这样 `renv::snapshot()` 才能扫描全书章节与计算实验，而不会遗漏该目录以外使用的包。

完整的恢复与依赖更新流程分别见 `environment/r/README.md` 和`environment/python/README.md`；不要只复制某个章节中的包安装命令。

### 目录与提交约定

例如线性模型模块可以保持下列目录布局：

```text
<项目根目录>/
├── .Rprofile                   # 提交：自动激活根目录的 renv
├── .renvignore                  # 提交：仅排除本机环境与生成输出
├── renv.lock                   # 提交：全书 R 依赖的唯一锁文件
├── renv/
│   ├── activate.R              # 提交：renv 引导文件
│   ├── settings.json           # 提交：renv 设置
│   └── library/                # 本机包库，不提交
├── environment/
│   ├── r/
│   │   └── README.md           # R 环境说明与上述布局的原因
│   └── python/
│       ├── .python-version     # 提交：固定 Python 解释器版本
│       ├── pyproject.toml      # 提交：直接依赖
│       ├── uv.lock             # 提交：精确依赖锁文件
│       └── .venv/              # 本机环境，不提交
└── statistics/Linear-model/
    ├── main.tex
    ├── computations.order
    └── computations/
        └── 01-linear-regression/
            └── r/
                ├── analysis.qmd
                └── analysis.html # 执行并渲染后生成，需要提交
```

`.gitignore` 会保留上述可复现所需的 R 与 Python 入口、设置与锁文件。各环境目录下的 `README.md` 分别说明首次恢复、依赖更新、锁定文件检查与提交边界；修改环境时应遵循对应 README，而不要只修改某一个章节的计算文件。

`computations.order` 使用普通 Markdown，不需要 JSON 或其他清单格式：

```markdown
# 线性模型计算实验

## 线性回归

- computations/01-linear-regression/r/analysis.html

## 复共线性与岭回归

- computations/02-multicollinearity-ridge/r/analysis.html

```

每个二级标题表示一个计算实验，标题出现的顺序决定网页编号。

### R/Python 的执行与 HTML 生成

每次渲染都会覆盖对应实验目录的 `analysis.html`；完成后按 `computations.order` 所列路径检查并提交该结果文件。

#### R / Quarto

`analysis.qmd` 使用全书根目录的 `renv`，需要配置 `embed-resources: true`。在 Positron 或其他支持 Quarto 的编辑器中打开该文件，然后直接点击 **Preview** 即可执行实验并生成同目录下的 `analysis.html`，不需要另行输入渲染命令。

#### Python / Jupyter + Pandoc

全书 Python 环境已在 `environment/python/pyproject.toml` 和 `uv.lock` 中锁定 Jupyter。

Python 计算实验分两步处理：UV 锁定的 Jupyter 只负责执行 Notebook，Pandoc 负责把已执行的 Notebook 生成与现有实验一致的、自包含的 HTML。

首先在 UV 锁定环境中执行 Notebook，并把新的单元格输出保存回 `.ipynb`：

```bash
PYTHONPATH="$PWD" uv run --project environment/python --locked jupyter nbconvert \
  --to notebook --execute --inplace \
  statistics/multivariate/computations/01-kmeans/python/analysis.ipynb
```

再使用 Pandoc 生成最终 `analysis.html`：

```bash
pandoc statistics/multivariate/computations/01-kmeans/python/analysis.ipynb \
  --from ipynb --to html --standalone --embed-resources \
  --output statistics/multivariate/computations/01-kmeans/python/analysis.html
```

将两条命令中的路径同时替换为实际实验路径。`--embed-resources` 会将 Notebook 输出的图片等资源嵌入 HTML；若 Notebook 还会读取数据文件，该数据文件仍需按项目约定提交。

所有需要绘图的 Python Notebook 都应调用根目录 `figure_settings.configure_matplotlib()`；需要绘图的 R/Quarto 实验应在隐藏的 setup 块中加载 `figure_settings/figures.R` 并调用 `configure_knitr_figures()`。两者都从 `html/build-config.toml` 读取统一图像策略，默认优先输出 SVG；Python SVG 还会移除运行时间元数据。R 的内置 SVG 设备依赖 Cairo/X11，在 macOS 的无界面渲染环境中不够稳定，因此公共配置会直接改用不依赖 XQuartz 的 Quartz 2× 高分辨率 PNG；其他系统在 Cairo 不可用时也会回退到高分辨率 PNG。不要在单个实验中重新覆盖这些公共参数。

### 插入教材网页

结果文件生成后，回到项目根目录执行：

```bash
python3 html/build.py
```

`build.py` 会：

- 查找与各章 `main.tex` 同目录的 `computations.order`；
- 根据二级标题和列表顺序生成案例编号；
- 提取每个 `analysis.html` 的正文，处理重复锚点与标题层级；
- 将结果追加到对应 chapter 的最后；
- 在 Quarto 渲染完成后插入最终 chapter HTML，保留原始公式、表格和图片；
- 为 Python/Jupyter 和 R/Quarto 增加统一的语言标签和教材样式；
- 在结果缺失或仍引用外部图片时给出明确错误并停止构建。

程序生成的 SVG 直接按矢量图导入；位图若声明了逻辑宽度，构建会校验其实际像素是否满足高分辨率屏幕所需的倍率，未声明逻辑宽度时才采用集中配置的绝对宽度下限。检查只决定构建是否通过，不会把图片尺寸或检查信息写入发布页面。直接由教材引用的外部图片仍按原文件复制，不会被重采样或重新编码。

提交和发布时，应提交 Notebook、QMD、`computations.order`、生成的`analysis.html`、根目录的 `.Rprofile`、`.renvignore`、`renv.lock` 与 `renv/` 中的引导/设置文件，以及更新后的 `html/site/`；不要提交 `renv/library/`、`.quarto/` 或 Notebook 缓存。Python 环境应提交`environment/python/.python-version`、`pyproject.toml`、`uv.lock` 与说明文件；不要提交 `environment/python/.venv/`。GitHub Pages 仍然只发布 `html/site/`，因此每次修改计算案例后都要先重新渲染结果，再执行网页构建。

## 发布到 GitHub Pages

项目使用 `.github/workflows/pages.yml` 发布已经在本地生成的`html/site/`。GitHub Actions 不会重新运行 Quarto，因此每次修改 `.tex`文件后，应先在本地构建，再提交和推送。

完整构建会在站点根目录写入只包含摘要值的 `.source-fingerprint`。Pages 工作流会在上传前核对它，避免构建输入已经变化却误发布旧的 `html/site/`；该文件不包含源码路径、图片尺寸或构建诊断。构建日期和“最近提交”属于构建时展示信息，不参与源码指纹；由于站点文件与源码在同一次提交中入库，包含本次站点更新的提交会在下一次构建时出现在提交列表中。

需要提交到 GitHub 的内容包括：

- 原始 LaTeX 文件和正文引用的图片、代码等资源；
- `html/build.py`、`html/build-config.toml`、`html/site_builder/`、`html/styles/`、`html/home.md`、`html/textbook-theme.js`、`html/textbook-toc.js`、`html/textbook-ui.js` 与 `html/favicon.svg`；
- `html/site-meta.json`、`html/chapter-progress.json` 与`html/notation-catalog.json`；
- 完整的 `html/site/`，包括 `index.html`、`chapters/`、`site_libs/`、`search.json` 和样式文件；
- `.github/workflows/pages.yml`。

`html/.build/`、LaTeX 编译临时文件和 `.DS_Store` 不需要提交，已经由`.gitignore` 排除。根目录 `.gitignore` 对 `html/site/` 中的 HTML 文件设置了例外，因此构建结果可以正常进入 Git。

### 第一次启用

先把项目推送到 GitHub：

```bash
python3 html/build.py
git add -A
git status
git commit -m "github.pages"
git push origin main
```

提交前检查 `git status`，其中应能看到 `html/site/index.html` 和`html/site/chapters/` 下的网页文件；如果看不到，不要提交，先检查`.gitignore`。

随后打开 GitHub 仓库的 `Settings` → `Pages`，在`Build and deployment` 中将 `Source` 设置为 `GitHub Actions`。推送到`main` 后，可以在仓库的 `Actions` 页面查看部署进度，也可以在该页面手动运行 `Deploy book to GitHub Pages` 工作流。

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

推送到 `main` 后，GitHub Actions 会自动用最新的 `html/site/` 覆盖线上版本。首页显示的编译日期是执行 `build.py` 时生成的日期。

如果本次修改涉及计算实验，应先在对应的 Python 或 R 环境中生成最新的`analysis.html`，再执行上述日常更新流程。

## 当前转换规则

- `part/chapter/section/subsection/subsubsection` 保留为对应网页层级。
- 暂存时自动启用 `main.tex` 中被注释的 `part` 和章节 `include`，但不修改原始 `main.tex`。
- `newtheorem` 声明会从 `settings.tex` 读取，定理环境按原父计数器编号。
- `proof` 保留为独立证明块，默认展开并允许逐个或整页折叠；折叠状态在当前浏览会话中保留，打印时始终显示证明正文。
- `label/ref/eqref/cref` 转换为网页内或跨页面链接。点击 `cref` 后来源链接会显示已访问状态，目标短暂高亮；紧随引用的 `(2)`、`(5.b)(5.c)` 等条目提示会纳入整条链接，并在跳转后说明应查看的具体项目。
- 浏览器后退或前进时会按最近标题与相对偏移恢复阅读位置。
- `equation/align/gather` 保留为 MathJax 数学环境。
- `enumerate/itemize` 中的显示公式会保留对应列表层级，公式后续条目不会被误判为代码块。
- 所有 `english.tex` 中的 `NewTerm` 都会进入术语表；总览提供 A–Z 导航，每个字母独立成页并按英文名称排序。
- 每条术语都建立独立搜索记录，搜索结果可直接跳到对应条目；重复索引键的不同定义会分别保留并显示来源。
- 左侧目录只显示“中英术语表”；A–Z 字母页通过总览卡片、前后导航和搜索访问，不占用侧栏长度。
- `gls{Key}` 按“中文（English）”显示，并链接到中英术语表。
- `qedhere` 交由网页证明块统一显示结尾方块，不再传给 MathJax。
- `\info/\unsure/\change/\improvement` 四类 `todonotes` 项目批注会保留为带颜色的网页内联提示，不再在转换时丢失内容。
- `algorithm` 与 `algpseudocode` 会转换为带标题、章内编号、行号和缩进的算法块；支持 `Require/Ensure/State/Statex`、条件、循环、函数、注释、`Call/Return` 以及 `label/cref` 算法引用。
- 行内数学公式通过 CSS 在左右各保留少量视觉间距，不修改原始 TeX 中的`$...$`；只有实际越过正文右边界的公式才会变成可横向滚动区域，普通公式的行高和基线不受影响。
- `minted` 和 `inputminted` 由 Pandoc 转成带语法高亮的代码块；后者引用的代码文件会自动复制到暂存目录。
- `densityplot` 环境在 PDF 中保留固定参数的 TikZ/PGFPlots 图，在网页中替换为可调整参数的 SVG 密度曲线；支持 PDF/CDF 切换、PDF 区间概率、坐标缩放和曲线对比。鼠标移入曲线区域时会显示当前位置与函数值；图表滚动到视口附近才加载数值计算、探针和绘图脚本。相关逻辑按加载器、数学计算、鼠标探针与图表界面拆分，脚本随静态站点一同发布，不依赖外部服务。
- 每个行间公式会保留转换前的原始 LaTeX；网页在公式右上角提供复制按钮，复制结果不会包含网页构建时生成的编号标签。
- 与章节同目录的 `computations.order` 控制 Jupyter/Quarto 结果的顺序，构建时自动编号并追加到相应 chapter 末尾。
- 右侧当前章目录会随正文滚动自动高亮，并保持当前条目可见。
- 每个正文页提供“在 GitHub 上报告本页问题”入口；首页和项目状态页提供源代码、错误报告、内容建议与提交记录入口。
- 项目状态页自动汇总章节进度、定理类环境、证明、算法、行间公式、交互图和术语数量，不需要手工维护统计数字。

站点发布校验错误在普通构建中就会导致失败；使用 `--strict` 会进一步让未定义术语或未解析引用导致构建失败：

```bash
python3 html/build.py --strict
```

## 目录

- `build.py`：稳定的命令行入口与构建阶段编排。
- `check_site_freshness.py`：发布前核对已生成站点与当前构建输入。
- `build-config.toml`：工具、路径、布局、图像质量和资源清单的集中配置。
- `site_builder/`：LaTeX 暂存、Pandoc AST、页面规划、QMD、计算结果、资源、Quarto、后处理、校验与发布模块。
- `styles/`：按基础视觉、页面骨架、内容组件、计算实验、首页、暗色、公式、交互图、响应式和项目页拆分的 CSS 源文件；构建时按配置合并为站点的 `style.css`。
- `../figure_settings/`：Python 计算实验共用的确定性 SVG/高 DPI 配置。
- `tests/`：使用 Python/Node.js 内置测试工具的构建与前端回归测试。
- `textbook-theme.js`：明暗主题状态、持久化与切换按钮。
- `textbook-toc.js`：右侧目录滚动高亮，以及当前一级目录分支的展开规则。
- `textbook-ui.js`：证明折叠、阅读位置、交叉引用提示与页面反馈入口。
- `site-meta.json`：发布日期、内容更新日期和 GitHub 仓库。
- `chapter-progress.json`：19 个正文章节的完成百分比。
- `.build/`：Pandoc AST、临时 `.qmd` 和 Quarto 工程，每次构建时更新。
- `site/`：最终静态网站，可发布到 GitHub Pages。
- `computations.order`：某一数学章节的计算实验标题与结果显示顺序。
- `.github/workflows/pages.yml`：从项目根目录发布 `html/site/` 的 GitHubPages 工作流。

默认调用 Positron 内置的 Quarto：

```text
/Applications/Positron.app/Contents/Resources/app/quarto/bin/quarto
```

如需使用其他版本，可以设置 `QUARTO` 环境变量。

## GitHub 语言统计

根目录 `.gitattributes` 将所有 `.html` 标记为不参与语言识别，并额外将生成站点与计算结果标记为生成文件。该设置必须提交到默认分支后 GitHub Linguist 才会采用；仓库语言条可能存在短暂缓存，但以后构建产生的 HTML 不会再把项目识别为 HTML项目。此规则只影响 GitHub 的语言统计，不影响 GitHub Pages 发布这些文件。
