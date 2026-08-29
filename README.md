<div align="center">

<img src="html/assets/favicon.svg" width="88" alt="项目标志">

<h1>你永远不知道一个强迫症能干出什么事情</h1>

<p><strong>一套 proof-first 的中文数学与统计学开放笔记</strong></p>

<p>从线性空间、测度论一路走到线性模型、时间序列、机器学习与因果推断。<br>
适合系统学习，也适合在忘记一个定义、定理或推导时随手查阅。</p>

<p><a href="https://expectorpatro.github.io/math/"><strong>在线阅读</strong></a> · <a href="https://expectorpatro.github.io/math/project-status.html">章节进度</a> · <a href="https://expectorpatro.github.io/math/notation.html">符号与记号</a> · <a href="https://expectorpatro.github.io/math/chapters/glossary.html">中英术语表</a></p>

<p>
<a href="https://github.com/Expectorpatro/math/actions/workflows/pages.yml"><img alt="GitHub Pages" src="https://img.shields.io/github/actions/workflow/status/Expectorpatro/math/pages.yml?branch=main&amp;label=website&amp;style=flat-square"></a>
<a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/github/license/Expectorpatro/math?style=flat-square"></a>
<a href="https://github.com/Expectorpatro/math/commits/main/"><img alt="Last commit" src="https://img.shields.io/github/last-commit/Expectorpatro/math?style=flat-square"></a>
</p>

</div>

> 我想做的不是一本只罗列结论的公式手册，而是一张可以沿着证明、概念联系和计算实验逐步走通的数学知识地图。

## 这套笔记想解决什么问题？

不同课程常把同一个数学对象讲成彼此割裂的片段：线性代数里的投影、分析学里的收敛、概率论里的条件期望、统计学里的估计与模型，其实始终在相互呼应。

这个项目尝试把本科阶段的数学与统计学知识重新组织为一套连贯体系：统一符号，保留完整推导，通过交叉引用连接前后知识，并用 Python/R 实验把抽象结论落到可以观察和复现的结果上。

目前项目包含 **19 个正文章节、700+ 条中英术语、500+ 份证明**，仍在持续修订和扩展中。

## 你可以在这里读到什么？

| 领域 | 已覆盖内容 |
| --- | --- |
| **代数** | 线性空间、线性映射、矩阵 |
| **分析学** | 度量空间、点列与映射、赋范线性空间、微分与积分 |
| **概率与测度** | 集合与集族、测度空间、可测函数、积分论、随机变量、期望、独立性 |
| **最优化** | 最优性理论、Newton 法、模拟退火与遗传算法等计算实验 |
| **统计学** | 点估计、假设检验、贝叶斯统计、统计计算、线性模型、多元统计、时间序列、机器学习与因果推断 |

各章完成度不同；想了解当前边界，可以查看实时维护的[项目进度页](https://expectorpatro.github.io/math/project-status.html)。

## 为什么值得读？

- **证明优先**：以逻辑闭环为目标，不满足于只给结论；除特别说明外，重要结果都会给出证明或推导。
- **跨课程连接**：通过统一记号和交叉引用，让代数、分析、概率和统计不再各自为战。
- **阅读体验完整**：在线版支持全文搜索、深色模式、移动端排版、公式复制、章节目录与 A–Z 双语术语索引。
- **理论与计算并行**：Python Notebook 与 R/Quarto 实验用于展示算法行为、数值结果和统计直觉，并提供可复现的依赖环境。
- **开放且持续更新**：LaTeX 源文件、网站构建器、勘误和修改历史全部公开。

## 从这里开始

第一次来，推荐直接打开[在线阅读版](https://expectorpatro.github.io/math/)，从前言或自己最关心的章节开始。遇到陌生符号时可以查[符号与记号说明](https://expectorpatro.github.io/math/notation.html)，遇到英文缩写或术语时可以查[中英术语表](https://expectorpatro.github.io/math/chapters/glossary.html)。

如果你更喜欢阅读源码，整本书的入口是 [`main.tex`](main.tex)，各主题分别位于 `algebra/`、`analysis/`、`probability-theory/`、`optimization/` 与 `statistics/`。

### 本地预览网站

网页构建需要 Python、Quarto、Pandoc、XeLaTeX、Ghostscript 与 Git。环境准备好后，在项目根目录运行：

```bash
python3 html/build.py --serve
```

然后访问 <http://127.0.0.1:8000/>。更完整的工具链、严格检查与计算实验说明见 [`html/README.md`](html/README.md)。

## 项目结构

```text
.
├── algebra/                 # 线性空间与矩阵
├── analysis/                # 度量空间与微积分
├── probability-theory/      # 测度、概率基础与渐近理论
├── optimization/            # 凸优化与启发式算法
├── statistics/              # 统计理论、模型与机器学习
├── appendix/                # 不等式、数域、矩阵与 R 函数附录
├── environment/             # Python / R 可复现环境说明
├── html/                    # 阅读网站、构建器与静态页面
├── main.tex                 # LaTeX 全书入口
└── ref.bib                  # 参考文献
```

## 欢迎一起完善

这是一套仍在生长的开放笔记。无论你是发现了一个错字、一个证明缺口、一处不统一的记号，还是愿意补充例题、图示、计算实验或完整章节，都非常欢迎参与。

你可以：

- 在 [Issues](https://github.com/Expectorpatro/math/issues) 中报告错误或提出内容建议；
- 在 [Discussions](https://github.com/Expectorpatro/math/discussions) 中讨论章节结构、证明思路与选题；
- 提交 Pull Request，修正内容或补充新的材料；
- 如果这套笔记对你有帮助，点一个 Star，让更多需要它的人看见。

提交内容时，请尽量说明修改涉及的章节、依据或参考资料。数学内容尤其欢迎指出隐藏条件、反例、符号冲突和推导中的跳步。

## 准确性与使用说明

本项目是持续修订中的个人数学笔记，并非经过同行评审的正式教材。若用于课程、研究或引用，请同时核对原始文献及标准教材。你也可以通过 [Issue](https://github.com/Expectorpatro/math/issues/new) 帮助修正问题。

## License

本项目采用 [MIT License](LICENSE) 开放。联系作者：<nxcexpect@163.com>。
