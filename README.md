# asp-validated-archimate-views-results

Per-run results of the benchmark behind the Scientific Students' Association (TDK) report
"Formally validated LLM-based view generation for ArchiMate models" (2026). The benchmark compares
the pipeline (P) with three baselines (B1, B2, B3) over 117 runs.

| File | Content |
|---|---|
| `results/results.csv` | one row per run: status, time, tokens, agent calls, repairs, judge rounds and verdicts |
| `results/views.csv` | one row per run: size of the generated view and its rule violations by category |
| `results/summary.csv` | one row per run: the values behind the report's tables |

The ArchiMate model and its rulebook come from an industrial project and are not public. The
generated views and the run logs reproduce large parts of the model, so they are not included
either, and the questions are given by id (`q02` … `q11`). The report describes the questions and
shows example views.
