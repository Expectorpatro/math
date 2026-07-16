# Project Style Guide

This reference distills conventions from the project's mathematical notes. Use it as a local style contract, not as a mandate to rewrite existing material.

## Project Shape

- Treat the source as Chinese mathematics/statistics notes built with `ctexbook`, not as a generic blog or a pure typesetting project.
- Keep chapter source in topic folders, with `main.tex` usually declaring `\chapter{...}` and sibling files declaring `\section{...}` and below.
- Keep global LaTeX behavior in `settings.tex`; do not introduce new packages, theorem environments, or macros unless the task truly requires it.
- Use `english.tex` files as glossary registries. The root `english.tex` holds broader terms; topic-local `english.tex` files hold chapter terms.
- Avoid editing generated files such as `html/site`, `.aux`, `.log`, `.out`, `.toc`, `.bbl`, `.bcf`, `.pdf`, `_minted`, and rendered images unless explicitly requested.

## Agent Scope

- This skill is an operating specification for agents working on mathematical notes, not a human-facing introduction and not a generic LaTeX formatting template.
- Use it for proof completion, proof repair, derivation checks, notation unification, symbol definition checks, logic gap review, glossary maintenance, and converting informal math prose into the project's LaTeX style.
- The goal is to continue the user's existing notes while raising rigor and maintainability. Do not turn the notes into a standard textbook voice or a list-heavy tutorial unless the user asks for that.
- When asked to "use my symbols", the current file and nearby statements are authoritative. Reuse the exact symbols already in the local argument, even if a global default elsewhere differs.
- When asked to "add after my paragraph" or "directly append", append a bridging sentence, proof paragraph, or environment only. Do not rewrite the preceding user text unless the user explicitly requests a rewrite.

## Source Review Protocol

- Before a nontrivial edit, inspect the nearest `.tex` file, the chapter `main.tex`, and the relevant local/root `english.tex` if terms are involved.
- For proof or logic tasks, search existing labels with `rg` before inventing a proof: look for the definition, theorem, property, lemma, inequality, model, or algorithm that already proves the needed fact.
- For symbol tasks, search the current file and sibling files for the symbol first. Preserve local meanings such as `\theta_0`, `\hat{\theta}_n`, `\ell(\theta,\mathbf{X})`, `P_X`, `\mathscr{F}`, or `\mathcal{M}(X)`.
- For macro or environment questions, read `settings.tex`. Do not assume a macro exists unless it is in `settings.tex` or already used in the surrounding source.
- If a result depends on a nearby unfinished `\info{...}` marker, keep the marker unless the task is to resolve it. If resolving it, replace it with the smallest rigorous proof or reference.
- Do not inspect files outside the project tree for style examples.

## Writing Voice

- Write in compact Chinese mathematical prose. The dominant pattern is definition or statement first, proof after.
- Prefer sentences like `设...，若...，则称...为...` for definitions and `设...，则：` for properties.
- Use `记：` before introducing notation, followed by display math when notation is central.
- Use `称...为\gls{...}` when the term should enter the bilingual glossary.
- Use direct proof transitions: `由...可得`, `根据...可知`, `于是`, `所以`, `综上`, `由...的任意性`, `立即可得`, `显然`.
- Existing notes sometimes say `略去证明`, `证明略去`, `显然`, or `直接验证即可`; preserve them when they are already present. Do not introduce new skip words for nontrivial steps unless a cited earlier result makes the step immediate.
- Keep the slightly personal explanatory tone in applied/statistics sections: short intuitive paragraphs may follow formulas, especially before a statistic, algorithm, or model interpretation.
- Do not over-polish into a generic translated textbook voice. Preserve the user's concise, proof-driven rhythm.

## Thinking Style

- Think in layers: define the object, record equivalent forms or immediate properties, prove existence/uniqueness/closure, then give interpretation or application.
- Reduce new claims to machinery already established in the project: previous `property` items, `\cref{...}(n)` references, linear equations, projections, rank/invertibility, generated sigma-fields, monotone or closure arguments, and normal equations.
- Prefer constructive proof over black-box citation when the construction teaches the notation. Show how the object is chosen, why it satisfies the required condition, and where uniqueness comes from.
- Preserve the proof moves that recur in the source: `任取...`, `注意到...`, `只需证明...`, `下证...`, `下求...`, `由...的任意性...`, `由此...`, `也就是说...`, `需要注意...`, `直观上...`, and `综上...`.
- Do not compress away intermediate algebra merely because the final identity is standard. The project often values the chain of equalities or inequalities as the explanation.
- In analysis and probability, favor generator/minimality reasoning: prove a class is a sigma-field, monotone class, closed set family, or linear space, show it contains a generator or dense subset, and conclude by minimality or closure.
- In linear algebra and statistics, favor structural reductions: decompose into subspaces, projections, ranks, normal equations, residual sums of squares, expectation/variance decompositions, and then interpret the result.
- In statistical testing or modelling sections, build the reader's memory path: define notation, derive the expectation or variance, identify the estimable/unbiased/statistic piece, state the rejection region or algorithm, then explain why the direction or threshold makes sense.
- Use `\info{...}` as precise memory hooks for missing lemmas, unclear intuition, or questions to revisit. Do not replace them with vague TODO comments.

## Mathematical Exposition Rules

- Do not only state the final conclusion. Preserve the route: object, condition, target, key construction, legal transformation, conclusion.
- When adding a derivation, first state what is being computed or proved, then introduce the notation needed for the computation, then show the formula chain.
- When a step uses a theorem, definition, property, lemma, inequality, model, or algorithm already in the project, cite it with `\cref{...}` whenever a suitable label exists.
- If the project already has a relevant theorem, do not repackage it under a new name. Reuse the existing wording or cite it, then add only the missing local bridge.
- For applied/statistical paragraphs, keep the user's habit of explaining why the statistic, rejection direction, projection, or decomposition is natural. A short `也就是说...` or `直观上...` paragraph is appropriate after the algebra.
- Do not automatically turn explanations into enumerated lists. Use `enumerate` for mathematical facts inside theorem-like statements; use natural paragraphs for motivation and interpretation.
- If the user provides informal text and asks for LaTeX notes style, convert it to theorem/proof/derivation/note structure only when the surrounding chapter uses that structure. Otherwise produce a natural paragraph plus displayed equations.

## Structural LaTeX

- Use tabs for indentation inside environments when editing nearby LaTeX that already uses tabs.
- Start theorem-like environments at the left margin:

```tex
\begin{definition}
	设$(X,\mathscr{A})$为可测空间。若...，则称...为\gls{MeasurableFunction}。
\end{definition}
```

- Prefer these environments:
  - `definition` for terms, objects, models, and notation.
  - `property` for numbered lists of facts and reusable lemmas that are not called theorems.
  - `theorem` for important named or structural results.
  - `proposition` only when the surrounding chapter already uses it or the result is explicitly framed as a proposition.
  - `lemma` and `corollary` for dependency chains.
  - `note` for interpretive comments, warnings, or informal memory aids.
  - `derivation` for auxiliary calculations that explain a formula.
  - `method` for algorithms or procedures.
  - `proof` after almost every nontrivial statement.

- Prefer `enumerate` for lists of mathematical facts:

```tex
\begin{property}\label{prop:Example}
	设...，则：
	\begin{enumerate}
		\item ...；
		\item ...。
	\end{enumerate}
\end{property}
```

- In proofs, write numbered branches as `(1)`, `(2)`, etc. directly in the prose. Use `\par` to separate proof steps when the surrounding file does.
- For necessity/sufficiency and existence/uniqueness, use:

```tex
\textbf{必要性：}...
\textbf{充分性：}...
\textbf{存在性：}...
\textbf{唯一性：}...
```

- Use `\qedhere` at the end of a final displayed equation when the proof ends inside display math.

## Preamble And Macros

- `settings.tex` is the only global preamble layer observed. Do not add packages, theorem environments, counters, colors, fonts, or macros unless the user asks or the mathematical content cannot be written with existing tools.
- Reuse the defined theorem environments: `definition`, `theorem`, `lemma`, `corollary`, `proposition`, `axiom`, `property`, `example`, `solution`, `remark`, `note`, `derivation`, `method`, and `proof`.
- Reuse project macros before inventing replacements:
  - `\dif` for differentials.
  - `\seq{x}{n}` for `x_1, x_2, \dots, x_n`.
  - `\info{...}`, `\unsure{...}`, `\change{...}`, `\improvement{...}` for project-local reminders.
- Use the `inequality` and `inequality*` environments for labelled inequalities when a durable inequality reference is needed.
- If a new command seems useful, first search whether the notation is already written explicitly in nearby files. Prefer explicit local LaTeX over adding a global macro for a one-off expression.
- Never use commands that are not provided by the current preamble unless they already appear in compiled source and their package is present.

## Labels And References

- Use `\cref{...}` rather than raw `\ref{...}` in prose.
- Put labels immediately on theorem-like begins when possible:

```tex
\begin{theorem}\label{theo:RadonNikodym}
```

- Use these label prefixes:
  - `def:` for definitions only when the definition will be referenced.
  - `prop:` for properties.
  - `theo:` for theorems.
  - `lem:` for lemmas.
  - `cor:` for corollaries.
  - `ineq:` for labelled inequalities.
  - `model:` for statistical models.
  - `alg:` for algorithms.
  - `tab:` for tables, rarely.

- Existing labels often use CamelCase or descriptive English fragments, for example `prop:MeasurableFunction`, `theo:NestedClosedBallsTheorem`, `ineq:Jensen`, `model:LinearModel`.
- Before adding a label, run `rg -F '\label{new-label}'`.
- When citing a numbered item in a property, write `\cref{prop:Name}(3)` or `\cref{prop:Name}(5.a)` to match the project.

## Glossary Terms

- Add terms with `\NewTerm` in the relevant `english.tex`.
- Use `\NewTerm[no acronym]` for ordinary terms and `\NewTerm[default]` for acronyms such as `MLE`, `CI`, `UMVUE`.
- Keep glossary keys in the existing mixed CamelCase style. Do not rename existing keys even if spelling is imperfect, such as `FoundamentalSeq`, `boarder`, or `NumberFiled`.
- Format entries as:

```tex
\NewTerm[no acronym] {MeasurableFunction}
{measurable function}
{可测函数}
```

- In the body, use `\gls{Key}` at the definition or first important mention:

```tex
则称$f$为从$(X,\mathscr{A})$到$(Y,\mathscr{B})$的\gls{MeasurableMap}。
```

- If adding a new term, check the root and local `english.tex` files first with `rg -F '{TermKey}'`.

## Math Display Style

- Prefer `equation*`, `align*`, and `gather*`. Use numbered `equation` only when the equation needs a durable reference.
- Use the custom `inequality*` environment for labelled inequalities:

```tex
\begin{inequality*}\label{ineq:Jensen}
	\varphi[\operatorname{E}(f|\mathscr{A})]\leqslant\operatorname{E}(\varphi\circ f|\mathscr{A})
\end{inequality*}
```

- Use `aligned` inside `gather*` or `equation*` when grouping several aligned blocks.
- Use `cases` for piecewise definitions, often inside `equation*`.
- Use `pmatrix` for matrices, `vmatrix` for determinants, and `array` for custom determinant/minor layouts.
- Use `\begin{gather*}` for several short formulas with no alignment target.
- Keep `\quad`, `\;`, and `\,` spacing habits near conditions:

```tex
\forall\;n\in\mathbb{N}^+,\quad i=1,2,\dots,n
```

- Prefer `\sum\limits`, `\lim\limits`, `\inf\limits`, and `\sup\limits` in displays when the surrounding file does.
- Prefer `+\infty` and `-\infty`, not `\infty` alone except for the extended-real shorthand already used.

## Formula Spacing And Micro-Typography

- In Chinese prose, inline math usually touches the surrounding Chinese text without literal spaces: write `记$\hat{y}=...` or `则$x\in A$` rather than adding English-style spaces around every `$...$`.
- Use `,\;` as the default separator for chained conditions inside one inline math fragment: `$A\in M_{m\times n}(K),\;B\in M_{n\times p}(K)$`, `$i=1,2,\dots,n,\;j=1,2,\dots,m$`.
- Use `\forall\;` and `\exists\;` in quantified formulas, especially in equivalence chains and definitions.
- Use `\quad` in display math to separate parallel statements, side conditions, and where-style clauses:

```tex
A^0=I_m,\quad A^n=A^{n-1}A,\quad n\in\mathbb{N}^+.
```

- In aligned displays, keep the visual spine on `&=`, `&\leqslant`, `&\iff`, etc.; use `&\quad` for continuation clauses when the line is explanatory rather than a new equality.
- Do not overuse `\,`. The project's stronger signature is semantic spacing with `\;` and `\quad`; add `\,` only when local readability or neighboring source already calls for it.
- Use `\text{...}` for Chinese words inside math, such as `\;\text{a.e.于}(X,\mathscr{F},\mu)` and short condition labels. Do not force these into English.
- Use `\left...\right`, `\Big...`, `\Big|`, and related delimiter sizes when grouping would otherwise be visually ambiguous. Do not mechanically scale every parenthesis pair.
- In numbered proof branches, preserve the small spacer after the branch marker when the file uses it: `(2)$\;A$...` or `\textbf{(1)$\;\mu$...}`.
- For displayed conditions that grow long, prefer `gather*`, `align*`, or one condition per line over dense inline math.

## Symbol Defaults

- Number systems:
  - `\mathbb{R}^{}` for scalar real line when the dimension slot is intentionally empty.
  - `\mathbb{R}^{n}`, `\mathbb{R}^{m}`, etc. for Euclidean spaces.
  - `\overline{\mathbb{R}^{}}` for extended real line.
  - `\mathbb{N}^+` for positive integers.
  - `\mathbb{C}^{}`, `\mathbb{Z}^{}`, `\mathbb{Q}` when needed.

- Inequalities and definitions:
  - Use `\leqslant` and `\geqslant`; avoid `\le` and `\ge` in new LaTeX.
  - Use `\coloneq` for definitions.
  - Use `\iff` or `\Leftrightarrow` for equivalences; use `\Longleftrightarrow` only when it visually helps.

- Greek variants:
  - Use `\varepsilon`, not `\epsilon`, for epsilon.
  - Use `\varphi` heavily for functions or signed measures.
  - Use `\varLambda` where the project uses capital Lambda matrices.
  - Use `\varliminf` and `\varlimsup` for lower and upper limits.

- Sets and sigma-fields:
  - Use `X` as ambient space, `A,B,C,E` as sets, and `I` as index set when generic.
  - Use `\mathscr{A}`, `\mathscr{F}`, `\mathscr{B}`, `\mathscr{P}`, `\mathscr{C}` for sigma-fields, set families, or probability/statistical structures.
  - Use `\mathscr{P}(A)` for power sets.
  - Use `\mathcal{B}` for Borel sigma-fields.
  - Use `\mathcal{M}` for column spaces or matrix-related spaces, and `\mathcal{T}` for transformations/operators.

- Sequences and tuples:
  - Use `\{x_n\}`, `\{A_n\}`, and `\{f_n\}` for sequences.
  - Use the project macro `\seq{x}{n}` for `x_1, x_2, \dots, x_n`.
  - Use `i=1,2,\dots,n` rather than `i=1,\ldots,n`.

- Differential and integrals:
  - Always use `\dif` for differentials: `\int_X f(x)\dif\mu`, `\dfrac{\dif P}{\dif\mu}`.
  - Use Radon-Nikodym derivatives as `\dfrac{\dif\varphi}{\dif\mu}`.

## Algebra And Linear Algebra Notation

- Use uppercase Latin letters for matrices: `A,B,C,X,Q`.
- Use lowercase Greek or Latin letters for vectors: `\alpha,\beta,\xi,x,y`.
- Use bold for special vectors and random vectors: `\mathbf{0}`, `\mathbf{1}_n`, `\mathbf{X}`.
- Use `^{\top}` for transpose and `^H` for Hermitian transpose.
- Use `A^-` for a generalized inverse and `A^+` for the Moore-Penrose inverse.
- Use `M_{m\times n}(K)` and `M_n(K)` for matrix spaces.
- Use `\operatorname{rank}`, `\operatorname{tr}`, `\operatorname{diag}`, `\operatorname{Ker}`, `\operatorname{Im}`.
- Use `||x||` for norms in existing style; do not normalize to `\lVert x\rVert` unless the surrounding file already does.
- Use `<\seq{\alpha}{n}>` for spans where existing algebra chapters use angle-bracket notation.

## Probability, Measure, And Statistics Notation

- Measure spaces:
  - `(X,\mathscr{A})` for measurable spaces.
  - `(X,\mathscr{F},\mu)` for measure spaces.
  - `(X,\mathscr{F},P)` for probability spaces.
  - Use `\mu`, `\nu`, `\varphi`, `P` for measures as the local chapter does.

- Almost everywhere and almost surely:
  - Write `\;\text{a.e.于}(X,\mathscr{F},\mu)`.
  - Write `\;\text{a.s.于}(X,\mathscr{F},P)`.

- Expectations and moments:
  - Use `\operatorname{E}`, `\operatorname{Var}`, `\operatorname{Cov}`, `\operatorname{Corr}`, not `E`, `Var`, or `\mathbb{E}`.
  - Conditional expectation appears as `\operatorname{E}(f|\mathscr{A})` or `\operatorname{E}(f\mid\mathscr{A})`; preserve local delimiter style.
  - Use indicator notation as `I_A(x)` or `I(x\in A)`.

- Random variables:
  - In measure-theoretic probability, random variables are often `f,g,h` on `(X,\mathscr{F},P)`.
  - In statistics chapters, use `X`, `Y`, `X_i`, `\mathbf{X}`, `y`, `\varepsilon`, and parameter vectors as already established.

- Distributions and models:
  - Use `X\sim\operatorname{N}(\mu,\sigma^2)`, `\operatorname{Binom}`, `\operatorname{Poisson}`, `\operatorname{F}`, `\operatorname{t}`.
  - Use `\operatorname{SSE}`, `\operatorname{RSS}`, `\operatorname{MSE}`, `SSA`, `SSe`, `MSe`, etc. according to local ANOVA/linear-model files.
  - For convergence, use existing forms such as `\overset{P}{\longrightarrow}`, `\overset{d}{\longrightarrow}`, and `\xrightarrow{P_{\theta_0}}`.

## Symbol And Object Discipline

- Define every new symbol at first use. The definition must include the object's type and home when relevant: set, event, sigma-field, measure, probability, random variable, sample, statistic, estimator, parameter, parameter space, density, function, matrix size, vector space, or function space.
- Do not change notation for the same object inside one argument. If the local file uses `\theta_0` for the true parameter, do not switch to `\theta^\ast`. If it uses `\ell(\theta,\mathbf{X})`, do not switch to `L_n(\theta)` unless the new normalized object is explicitly defined.
- If introducing a normalized or indexed variant, define the relationship:

```tex
\ell_n(\theta)=\ell(\theta,\mathbf{X})=\sum_{i=1}^{n}\log p_\theta(X_i),\quad
M_n(\theta)=\frac{1}{n}\ell_n(\theta).
```

- For samples, distinguish the single observation `X`, coordinate variables `X_i`, the sample vector `\mathbf{X}`, a statistic `T(\mathbf{X})`, and the sample distribution or joint law.
- For dominated models, state the dominating measure and density: `p_\theta=\dfrac{\dif P_\theta}{\dif\mu}` or the local equivalent.
- For events, state membership such as `A\in\mathscr{F}` before using `P(A)`, `I_A`, conditional probabilities, or set limits.
- For indicators, preserve local notation: `I_A(x)`, `I(x\in A)`, or `I_A` according to the surrounding file.
- For function spaces, state the measure space: `L_1(X,\mathscr{F},\mu)`, `L_2(X)`, `l^1`, etc. Do not write a bare `L_1` if the measure is ambiguous.
- For matrices, define dimensions before formulas that require conformity: `A\in M_{m\times n}(K)`, `X` is `n\times p`, `\beta` is `p\times1`, etc.
- For probability modes, keep notation exact:
  - `f_n\overset{\text{a.s.}}{\longrightarrow}f` or local `a.s.` wording for almost sure convergence.
  - `f_n\overset{P}{\longrightarrow}f` for convergence in probability.
  - `f_n\overset{d}{\longrightarrow}f` for convergence in distribution.
  - `\xrightarrow{P_{\theta_0}}` when the probability law is explicitly indexed by the true parameter.

## Proof Patterns

- For definitions, start from the ambient object and end with a name:

```tex
\begin{definition}
	设$(X,\mathscr{A})$是可测空间，$f:X\to\mathbb{R}$。若...，则称$f$为\gls{MeasurableFunction}。
\end{definition}
```

- For reusable facts, use a property with a list:

```tex
\begin{property}\label{prop:Example}
	设...，则：
	\begin{enumerate}
		\item ...；
		\item ...。
	\end{enumerate}
\end{property}
\begin{proof}
	(1)由\cref{prop:Other}(2)立即可得。\par
	(2)任取...，于是...。由...的任意性，结论成立。
\end{proof}
```

- For equivalence chains, use compact alignments:

```tex
\begin{align*}
	x\in\varliminf_{n\to+\infty}A_n
	&\iff \exists\;N\in\mathbb{N}^+,\;\forall\;n\geqslant N,\;x\in A_n.
\end{align*}
```

- For estimates, show the chain rather than only citing a theorem:

```tex
\begin{align*}
	\operatorname{E}(\operatorname{SSE})
	&=\operatorname{E}[y^{\top}(I_n-P_X)y] \\
	&=\sigma^2\operatorname{tr}(I_n-P_X).
\end{align*}
```

- End proofs with `综上，...。` when several cases were combined.

## Proof Rigor Rules

- Before writing a proof, identify the statement type: equality, inclusion, measurability, integrability, convergence, existence, uniqueness, optimality, unbiasedness, or asymptotic result. Then check the exact hypotheses needed for that type.
- Do not write `显然`, `易知`, `不难得到`, or `直接可得` for a nontrivial step unless a nearby `\cref{...}` makes it genuinely immediate.
- When using a theorem or property, cite the exact labelled result and item number if available, for example `由\cref{prop:MeasurableFunction}(6)可知...`.
- For set equalities, prove both inclusions unless the equality is a direct named identity already cited. Use `任取...` and `由...的任意性...` as in the notes.
- For closure statements, verify the defining operations one by one: nonempty or contains `X`, complement or difference, finite/countable union or intersection, scalar addition/multiplication, etc.
- For generated sigma-field arguments, use the project's pattern: define a class, prove it is a sigma-field/monotone class/lambda-system, prove it contains the generator, then conclude by minimality.
- For measurability, state the domain and codomain measurable spaces and show preimages/generators or cite an existing measurable mapping/function property.
- For integration, expectation, conditional expectation, and covariance, first ensure the object is measurable and has the required integrability or nonnegative extended-valued status.
- For conditional expectation, distinguish conditioning on a sub-`\sigma`-field from conditioning on a random variable: `\operatorname{E}(f|\mathscr{A})` versus `\operatorname{E}(f|g)=\operatorname{E}[f|\sigma(g)]`.
- For a.e. and a.s. statements, name the underlying measure/probability space when ambiguity is possible: `a.e.于$(X,\mathscr{F},\mu)$` or `a.s.于$(X,\mathscr{F},P)$`.
- Do not mix pointwise, a.e., a.s., in probability, in distribution, uniform, or `L_p` convergence. If changing mode, cite the theorem or prove the implication.
- For limit/integral/expectation interchange, state the tool: monotone convergence/Levi, Fatou, dominated convergence, uniform convergence, Fubini/Tonelli, or an existing project theorem.
- For compactness or extreme value arguments, explicitly state compactness/closedness/boundedness and continuity before claiming a maximum, minimum, convergent subsequence, or finite subcover.
- For Radon-Nikodym arguments, state the measure space, sigma-finiteness/finite assumptions, absolute continuity `\ll`, and uniqueness mode before writing the derivative.
- For MLE consistency/asymptotic normality, do not invoke the result without regularity conditions: parameter space, true parameter, identifiability or unique maximizer, continuity/differentiability, uniform convergence or LLN, information nonsingularity, and the convergence mode.
- For linear algebra/statistics proofs, preserve the rank/projection/normal-equation route when the surrounding chapter uses it; show why matrices are invertible, generalized inverses are well-defined, or expressions are independent of the chosen generalized inverse.

## Tables, Algorithms, Figures, Code

- Tables usually use:

```tex
\begin{table}[H]
	\centering
	\begin{tabularx}{\textwidth}
		{>{\centering\arraybackslash}c|*{5}{>{\centering\arraybackslash}X}}
		\toprule
		来源&平方和&自由度&均方和&F值 \\
		\midrule
		...
		\bottomrule
	\end{tabularx}
	\caption{...}
\end{table}
```

- Algorithms use `algorithm` plus `algorithmic`, with English command text acceptable:

```tex
\begin{algorithm}
	\caption{Gaussian Elimination}
	\label{alg:gauss}
	\begin{algorithmic}[1]
		\Require ...
		\Ensure ...
		\State ...
	\end{algorithmic}
\end{algorithm}
```

- Code examples in LaTeX should use the existing `minted` package only if the surrounding chapter already uses code blocks or the task asks for code display.
- TikZ is present but rare. Prefer simple mathematical exposition unless a diagram is genuinely useful.

## Markdown Notes

- Markdown notes are less canonical than `.tex` chapters. Treat them as study notes or scratch explanations unless the task specifically asks to polish Markdown.
- Common Markdown style:
  - Chinese headings with `#`, `##`, `###`.
  - Bold key claims with `**...**`.
  - Display math with `$$` and often `align*`.
  - Code fences for Python/C++ examples.
  - Casual explanatory paragraphs and occasional direct questions.
- When converting Markdown to LaTeX, translate the useful content into the stricter LaTeX conventions above instead of preserving Markdown looseness.

## Editing Existing Notes

- Prefer the smallest diff that repairs the mathematical issue. Do not reorder unrelated paragraphs, renumber structures, rename labels, or normalize style across a whole file unless asked.
- Keep the user's original Chinese phrasing when it is mathematically correct. Improve local precision without turning the paragraph into generic textbook prose.
- If a proof has a gap, first identify the exact gap in your response, then provide a directly pasteable LaTeX repair that fits the existing proof route.
- If several proof routes are possible, choose the one closest to the user's current construction and notation. Do not replace a projection proof with an unrelated convexity proof, or a generator proof with a measure-class theorem, unless the local route is wrong.
- When local notation is inconsistent with a global preference, preserve local notation and mention the inconsistency only if it affects correctness or future maintenance.
- Preserve labels and `\cref` targets. If a label is wrong or duplicated, report it and make the smallest label fix.
- Do not delete `\info{...}` or draft comments unless resolving exactly that issue. If the task resolves it, replace it with the rigorous content and remove only the resolved marker.
- Do not introduce new macros, theorem environments, or packages while editing ordinary notes. Use explicit LaTeX with existing commands.
- Do not rewrite a whole theorem/proof because a single condition is missing. Add the missing hypothesis and the minimal explanatory step.

## Output Boundaries

- For complete pasteable additions, output valid LaTeX code with the surrounding environment if needed.
- For conceptual explanation, start with natural language, then give only the formulas needed to make the point precise.
- Do not output broken plain-text formulas. Use renderable LaTeX math.
- Do not automatically make everything a bullet list. Use continuous paragraphs by default; use lists only when the mathematical object is itself a list of conditions or facts.
- If reviewing or repairing logic, separate "问题在哪里" from "可粘贴修补版本" so the user can see the mathematical reason and the concrete fix.
- If the user asks for a direct edit in the repository, make the edit rather than only giving advice, subject to the project-only and minimal-diff rules.

## Uncertainty Handling

- If no matching macro, label, glossary term, or theorem is found in the project, do not pretend it exists. Use the nearest existing expression or state that no project definition was found.
- If a statement requires extra hypotheses, add the weakest local hypotheses you can justify and explain why they are needed.
- If a user-provided theorem is false as stated, say so plainly, give a counterexample or identify the missing condition, and then provide a minimally corrected version.
- If a proof depends on an external theorem not yet present in the notes, either cite it only as an external named theorem in prose or add a precise `\info{...}` marker asking to introduce it later. Do not create a fake `\cref` label.
- If the local notes are internally inconsistent, follow the current file for the immediate edit and mention the conflict in the response.
- If compilation cannot be run, still check for syntactic issues locally and state that compilation was not performed.

## Editing Checklist

- Check nearby notation before adding a symbol, and verify every new symbol has been defined.
- Check `english.tex` before adding a glossary term, and use `\gls{...}` at the definition or first important mention.
- Check labels with `rg` before adding one; use `\cref`, not raw `\ref`, except in tables or legacy local style where `\ref` already dominates.
- Check whether an existing theorem/property/lemma already proves the needed step before re-proving it.
- Check that each proof states the needed hypotheses: measurability, integrability, finiteness, sigma-finiteness, compactness, closedness, continuity, independence, rank, invertibility, or regularity assumptions as applicable.
- Check that no pointwise/a.e./a.s./in probability/in distribution/uniform/`L_p` statement has been mixed without explanation.
- Check that conditional expectations and probabilities specify whether conditioning is on a random variable or a sub-`\sigma`-field.
- Check that samples, parameters, parameter spaces, densities, dominating measures, statistics, and estimators are not conflated.
- Check formula spacing against local style: inline Chinese math attached to text, `,\;` for chained conditions, `\quad` for display-side conditions, and no unnecessary `\,`.
- Check for unclosed environments, unmatched braces, undefined commands, undefined labels, duplicated labels, and newly introduced macros not present in `settings.tex`.
- Check that the edit does not break chapter structure, labels, glossary registries, or existing `\info{...}` markers.
- Run the project build command such as `xelatex`/the repository's documented build path when feasible and relevant. If not run, report that explicitly.
- Do not normalize all existing style inconsistencies in unrelated files.
- Do not replace the user's preferred symbols with common alternatives such as `\mathbb{E}`, `\le`, `\ge`, `\epsilon`, `\ldots`, `\mathrm{d}`, or a different dimension/operator notation when the local chapter uses another form.
