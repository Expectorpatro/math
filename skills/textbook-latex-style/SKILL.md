---
name: textbook-latex-style
description: Write, edit, review, or extend this project's large mathematical LaTeX notes in the user's established notation, proof, citation, glossary, and technical writing style. Use when Codex works on this project for .tex chapters, mathematical exposition, proof completion, proof review, symbol unification, logical gap checks, equations, cross-references, glossary terms, tables, algorithms, or technical Markdown notes.
---

# Mathematical Notes LaTeX Style

## Core Workflow

1. Work only inside the project tree. Do not inspect the user's other folders when refreshing examples or looking for conventions.
2. Before editing, read the nearest source file, its chapter `main.tex`, the relevant `english.tex`, and `settings.tex` if the change touches environments, macros, references, or terms.
3. For proof, notation, or rigor tasks, inspect the local definitions, labels, symbols, and previously proved results before writing new text.
4. Preserve local convention over general LaTeX taste. Add the smallest change that blends into the surrounding chapter.
5. Use `rg` to check existing labels, glossary keys, notation, theorem names, and macros before introducing anything new.
6. Avoid generated outputs (`html/site`, `.aux`, `.log`, `.pdf`, `_minted`) unless the task is explicitly about build artifacts.

## Style Reference

Read `references/project-style-guide.md` before any nontrivial writing task, especially when:

- adding a definition, theorem, property, proof, note, derivation, method, table, algorithm, or figure;
- completing or repairing a proof;
- checking a derivation for hidden assumptions, undefined variables, circular references, or invalid limit/integral/exchange steps;
- converting informal reasoning into LaTeX mathematical notes;
- unifying notation for a definition, theorem, estimator, statistic, sigma-field, measure, or model;
- choosing symbols for sets, sigma-fields, probability spaces, random variables, matrices, vectors, estimators, or limits;
- adding or using glossary terms with `\NewTerm` and `\gls`;
- translating Markdown notes into the project's LaTeX notes style;
- reviewing whether generated LaTeX feels like the existing notes.

## Notation Contract

Before adding, changing, reviewing, or unifying mathematical notation, read
`references/notation-catalog.json` in full. This catalog is the shared source
for both the website's “符号与记号说明” page and agent behavior.

- Reuse its preferred forms for new content, including `\dif`,
  `\operatorname{E}`, `\varepsilon`, `\leqslant`, `\geqslant`, `\seq`, and
  `^{\top}`.
- Treat every entry in “依语境使用的符号” as context-sensitive. Never
  mass-replace symbols such as `X`, `P`, `I`, `L`, `\mu`, `\lambda`, `\rho`,
  `\mathscr{P}`, or `\mathcal{B}`.
- Local definitions and the nearest consistent usage override a global
  default. If a local convention legitimately differs, preserve it and make
  the object's meaning explicit rather than forcing visual uniformity.
- The catalog's `avoid` values are review signals. They do not authorize a
  blind textual rewrite of existing sources.
- When a durable new convention is approved, update the catalog first so the
  generated website and future agents receive the same rule.

## High-Signal Defaults

- Write Chinese mathematical exposition with dense but readable notes structure. Keep occasional English theorem names, model names, and algorithm names when the project already does so.
- Treat the skill as an operating manual for agents, not a human-facing math introduction. Prefer concrete actions: read local context, reuse labels, define symbols, state conditions, and make minimal edits.
- Prefer `definition`, `property`, `theorem`, `lemma`, `corollary`, `proposition`, `note`, `derivation`, `method`, and `proof` environments already defined in `settings.tex`.
- Prefer `\cref{...}` for cross-references and label prefixes such as `prop:`, `theo:`, `lem:`, `cor:`, `ineq:`, `model:`, and `alg:`.
- Prefer unnumbered display math (`equation*`, `align*`, `gather*`) unless a reference is needed. Use `inequality*` for labelled inequalities.
- Preserve the project's formula spacing habits: inline Chinese prose usually attaches directly to `$...$`; use `,\;` to separate chained inline conditions, `\forall\;` and `\exists\;` for quantified clauses, and `\quad` for parallel clauses or conditions in display math.
- Mirror the user's proof rhythm: define the object, reduce it to known structures, cite earlier results with numbered items, show the algebraic chain, then add intuition or interpretation when it helps memory.
- Use project notation: `\dif` for differentials, `\leqslant` and `\geqslant`, `\coloneq`, `\operatorname{E}`, `\operatorname{Cov}`, `\operatorname{Var}`, `\operatorname{rank}`, `\mathscr{F}`, `\mathscr{A}`, `\mathbb{R}^{}`, `\mathbb{N}^+`, and `\seq{x}{n}`.
- Every new mathematical object must have a home: space, sigma-field, parameter space, sample, distribution, measure, density, function class, matrix size, or event membership as applicable.
- Do not silently mix pointwise, a.e., a.s., in probability, in distribution, uniform, or $L_p$ statements. State the mode and the conditions that justify changing modes.
- Keep unfinished reminders in the project's style with `\info{...}` or the existing todo macros, not generic placeholder comments.
