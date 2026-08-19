# Adapting the Stevens LaTeX template for the DRIFT thesis

Requirements verified against the Stevens Library formatting guidelines and the master's sample pages, August 2026. Sources at the bottom.

**The content is already written.** [`paper/thesis/`](thesis/) contains a complete, compiled-and-verified drop-in for your Overleaf project: `chapter1.tex` through `chapter6.tex`, `appendixA.tex` (complete per-cell results and the full significance matrix), `appendixB.tex` (figures, dataset schema, reproduction commands, integration example), `references.bib` (all 14 sources), the ten figures it references, and an updated `stevensDissertation.tex` that includes all of it. It builds cleanly with `pdflatex` end to end. `titlepg.sty` and `pgnumchapter_nums.sty` are included unmodified, since you are editing the title page yourself; `paper/thesis/FRONT_MATTER_DRAFT.md` has a ready-to-paste abstract (345 words), plus draft dedication and acknowledgments text, for the parts of `titlepg.sty` that are content rather than personal information. Upload the contents of `paper/thesis/` into your Overleaf project, overwriting the sample files, and you have a full first draft.

**The single most important thing left:** the template you imported is set up for a **PhD dissertation**. You are writing a **master's thesis**. That changes the title page wording, the degree line, and the number of committee signature lines. Fix that first, in `titlepg.sty`, because the Library must approve your title page before you can collect signatures.

---

## 1. Fix `titlepg.sty` first

Replace the placeholder fields with these. The `\thesistype` and `\thesisdegree` values are what switch the page from dissertation to thesis.

```latex
\newcommand{\thesistitle}{DRIFT: Decay Rates in Forgetful Bitemporal Memory}
\newcommand{\thesisyear}{2026}
\newcommand{\thesisname}{Nandan Hemanth}
\newcommand{\thesischairadvisor}{Hao Wang}   % prints as Advisor on both pages
\newcommand{\committeenameA}{...}            % your Reader
\newcommand{\thesisdepartment}{Computer Science}
\newcommand{\thesisdate}{...}                % your defense date
\newcommand{\thesistype}{thesis}
\newcommand{\thesisdegree}{Master of Science}
```

Then delete `\committeenameB`, `\committeenameC` and `\committeenameD`, and remove the corresponding signature lines from the title page body further down the file. A master's title page carries **two** signatures, not five:

```
___________________________________________
Nandan Hemanth, Candidate

ADVISORY COMMITTEE

___________________________________________
Hao Wang, Advisor                      Date

___________________________________________
[Reader name], Reader                  Date
```

Also check the body of `titlepg.sty` for the literal strings `A DISSERTATION` and `DOCTOR OF PHILOSOPHY`. The sample master's page reads:

```
A THESIS

Submitted to the Faculty of the Stevens Institute of Technology
in partial fulfillment of the requirements for the degree of

MASTER OF SCIENCE - COMPUTER SCIENCE
```

Confirm the exact degree wording with your program director. It must match your transcript.

---

## 2. Files to keep, edit and delete

| File | Action | Notes |
|---|---|---|
| `stevensDissertation.tex` | **Already done**, in `paper/thesis/` | Rewired to `\include` all six chapters and both appendices, bibliography fixed to `\bibliography{references}`, the doctoral-only Vita section removed. Content beyond the title-page block is unchanged from the sample. |
| `titlepg.sty` | **Edit yourself** | Section 1 above. Do this first. A copy is included in `paper/thesis/` for convenience, unmodified from what you uploaded. |
| `pgnumchapter_nums.sty` | **Keep, unmodified** | Implements the required numbering: roman front matter, arabic body, both top right. A copy is included in `paper/thesis/`. |
| `references.bib` | **Already done**, in `paper/thesis/` | All 14 sources, identical to `paper/references_for_thesis.bib`. |
| `chapter1.tex` through `chapter6.tex` | **Already written**, in `paper/thesis/` | Introduction, Related Work, Method, Experimental Setup, Results, Discussion and Conclusion, adapted from `paper/REPORT.md` with expanded Related Work and Method sections as a thesis expects. |
| `appendixA.tex` | **Already written**, in `paper/thesis/` | Complete per-cell results (all four benchmarks run) and the full 21-pair McNemar significance matrix, in landscape tables. |
| `appendixB.tex` | **New file**, in `paper/thesis/` | Figure index, dataset schema, exact reproduction commands, and the DRIFT integration example. Add `\include{appendixB}` after `\include{appendixA}` if you are not starting from the provided `stevensDissertation.tex`. |
| `symbols.tex` | **Optional, not used** | Not required by Stevens and not referenced by the provided chapters. |
| `myrefs.bib` | **Not present** | The uploaded project did not include this file; the main file's `\bibliography{}` line now points at `references.bib` instead. |
| `3d-cone.pdf`, `sin_x.jpg`, `oddsinx.gif` | **Not present** | The uploaded project did not include these; none of the new chapters reference them. |

**One thing to watch for at compile time.** `stevensDissertation.tex` keeps the template's original `\bibliographystyle{chicago}`. This requires the CTAN `chicago` package, which is part of Overleaf's full TeX Live distribution and should already be available, but if you ever see `chicago.bst` reported as missing, the one-line fix is to change that command to `\bibliographystyle{plainnat}`, which ships with every LaTeX install and was used to verify that every citation in the new chapters resolves correctly against `references.bib`.

**Before deleting anything**, run a search across the project for the filename. Overleaf's search is the magnifying glass in the editor toolbar. If the main file still `\include`s or `\includegraphics` a file you removed, compilation breaks with a confusing error.

You will need four more chapter files. Create `chapter3.tex` through `chapter6.tex` and add matching `\include` lines in the main file.

---

## 3. Required order of sections

Stevens checks this. Do not reorder.

| # | Section | Page number |
|---|---|---|
| 1 | Title page | none |
| 2 | Copyright page | none |
| 3 | Abstract | roman, starts at **iii** |
| 4 | Dedication | optional, roman |
| 5 | Acknowledgments | optional, roman |
| 6 | Table of Contents | roman |
| 7 | List of Tables | roman, and you have many tables |
| 8 | List of Figures | roman, and you have many figures |
| 9 | Main body | **arabic, restarts at 1** |
| 10 | References / Bibliography | arabic |

**Vita is doctoral only.** If the template includes a Vita section, delete it.

Copyright page content:

```
© 2026, Nandan Hemanth. All rights reserved.
```

The year must match the title page.

---

## 4. Formatting rules

| Rule | Requirement |
|---|---|
| Margins | Left and top **1.5 inches**; right and bottom **1 inch**, throughout |
| Front matter numbering | Lowercase roman, **top right**, starting at iii |
| Body numbering | Arabic, **top right**, restarting at 1 |
| Figures and tables | Must sit inside the margins |
| Abstract length | **350 words or fewer** |
| Abstract trailer | Ends with Author, Advisor, Date, Department, Degree |

The template should already implement the margins and numbering. Verify by compiling and checking a page from each section, rather than assuming.

**Your results tables will overflow.** The headline table has 7 columns and Appendix A has 11. Use `\small` or `\footnotesize` inside the table environment, or `\begin{landscape}` from the `pdflscape` package for the widest ones. The Library rejects submissions with content outside the margins.

---

## 5. Mapping REPORT.md onto thesis chapters

Your `paper/REPORT.md` already contains everything. This is a reorganisation, not new writing.

| Chapter | Source in REPORT.md | Rough length |
|---|---|---|
| Abstract | Abstract, cut to 350 words | 1 page |
| 1. Introduction | Section 1 entire, plus section 3 (Novelty) folded into 1.5 | 6 to 8 pages |
| 2. Related Work | Section 2, expanded. A thesis expects more depth than a paper. | 8 to 12 pages |
| 3. Method | Section 4 entire | 10 to 14 pages |
| 4. Experimental Setup | Section 5 entire. Section 5.1 (the benchmark negative result) deserves its own subsection. | 8 to 10 pages |
| 5. Results | Sections 6.1 to 6.13 | 15 to 20 pages |
| 6. Discussion and Conclusion | Sections 7, 8, 9, 10, 11, 12 | 10 to 14 pages |
| Appendix A | Appendix A (per-cell tables), section 6.12 (significance matrix) | 6 to 10 pages |
| Appendix B | Appendices C, D, E (schema, reproduction, integration) | 4 to 6 pages |

That lands around 70 to 95 pages, which is normal for a master's thesis in this area.

**What to expand relative to the paper.** A thesis is judged partly on demonstrated understanding, so Related Work and Method should be longer and more explanatory than a conference version. Your Discussion (section 7 of REPORT.md) is already thesis-grade; keep it in full.

**What to keep exactly as written.** The statistics, all tables, the threats to validity, and the judge audit. Do not soften any of it.

---

## 6. Figures to include

All are already generated at 300 dpi in this repository.

| Figure | Path | Chapter |
|---|---|---|
| Pipeline architecture | `artifacts/results/mquake_t/report_pack/architecture.png` | 3 |
| Accuracy and staleness | `artifacts/results/{factconsolidation,mquake_t}/figures/accuracy_staleness.png` | 5 |
| Trade-off scatter | `.../figures/tradeoff_scatter.png` | 5 |
| Memory growth | `.../figures/memory_growth.png` | 5 |
| Token cost | `.../figures/token_cost.png` | 5 |
| Per-model comparison | `.../figures/model_comparison.png` | 5 |
| Policy radar | `.../report_pack/radar_policies.png` | 5 |
| Baseline versus DRIFT | `.../report_pack/baseline_vs_drift.png` | 5 |
| Swarm topology | `artifacts/results/swarm_smoke/figures/swarm_topology.png` | 5 |

Upload the PNGs to Overleaf in a `figures/` folder. PNG compiles fine under pdfLaTeX.

---

## 7. Order of work

1. Fix `titlepg.sty`, compile, and submit the single-page title PDF to ProQuest ETD for formatting approval. **Do this now**, before writing anything. Approval is required before your defense and takes 1 to 2 business days per review.
2. Delete the sample figures and `myrefs.bib`, after searching for references to them.
3. Drop in `references_for_thesis.bib` and confirm citations resolve.
4. Build the chapter skeleton with section headings only, and compile. Fixing structure is cheaper before the text exists.
5. Fill chapters from REPORT.md.
6. Write the abstract last, to the 350-word limit.

---

## 8. Things that are outside the Library's remit

The Library approves formatting only, not content. Your advisor and program director handle the defense process and signature collection. For master's students specifically, the guidelines say to coordinate with your advisor and program director rather than with Graduate Academics.

Submission goes through ProQuest's ETD Administrator. Filing for copyright there is optional. The binding fee is paid through the Library's payment portal, not in ETD, and covers three bound copies: two for your department and one for the archives. You do not receive a personal copy.

---

## Sources

- Stevens sample pages: <https://www.stevens.edu/sample-pages>
- Formatting and submission guidelines, master's and PhD: <https://assets.ctfassets.net/mviowpldu823/4UXwc7cf1ndEw3elUE4DdC/8f3cce3d203c8dc04685a76cc2a893ff/2023_gradthesisdissertationsubmission.pdf>
- Library submission page: <https://library.stevens.edu/submit>
- Master's thesis title page sample: <https://assets.stevens.edu/mviowpldu823/68cycUr0oq5KyO8tSVIHcD/6b74dbb87abcfae138838ff4fc398b33/mstex_4.pdf>
- Master's abstract sample: <https://assets.stevens.edu/mviowpldu823/xqOwij0eQbAqJwUFFfjDv/a917da7192910a378d27e1008edd4fbb/abstrms_3.pdf>
- Copyright page sample: <https://assets.stevens.edu/mviowpldu823/5dvGygNU6DBA9FkpgHEwRQ/2731b2899c664aae3fc266f8a9a7f425/copyright_2.pdf>
- LaTeX template origin: <https://fsc.stevens.edu/stevens-dissertation-latex-template/>
