# asp-validated-archimate-views-results

Per-run results of the benchmark behind the Scientific Students' Association (TDK) report
"Formally Validated LLM-Based View Generation for Complex Engineering Models" (2026), and a
public version of the pipeline. The benchmark compares the pipeline (P) with three baselines (B1, B2,
B3) over 117 runs.

## Results

| File | Content |
|---|---|
| `results/results.csv` | one row per run: status, time, tokens, agent calls, repairs, judge rounds and verdicts |
| `results/views.csv` | one row per run: size of the generated view and its rule violations by category |
| `results/summary.csv` | one row per run: the values behind the report's tables |

The ArchiMate model and its rulebook come from an industrial project and are not public. The
generated views and the run logs reproduce large parts of the model, so they are not included
either, and the questions are given by id (`q02`, `q04`, `q07`, `q08`, `q10`, `q11`). The report
describes the questions and shows example views.

## Pipeline

This is the pipeline of the report without the parts specific to its case study. It comes with a
small fictional example model. The numbers in `results/` cannot be reproduced with it.

You need Python 3.11 or newer, [Claude Code](https://claude.com/claude-code) (logged in with a
Claude subscription or an API key) and
[draw.io desktop](https://github.com/jgraph/drawio-desktop/releases) (`drawio` on the `PATH`).

```bash
cd pipeline
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests   # checks the ASP gates, no LLM calls
.venv/bin/python scripts/run.py intents/checkout_payment.md --model haiku
```

The result is `pipeline/runs/P/<run>/4_render.png`. `--model` sets the model of the three generation steps.
The judge is set in `pipeline/pipeline.toml` and is Opus by default, also with `--model haiku`.

To use your own ArchiMate model, save it from Archi as `pipeline/data/model/model.archimate`, export
it, and write a question into a file in `pipeline/intents/`. Element names must be unique.

```bash
cd pipeline
.venv/bin/python scripts/export_facts.py data/model/model.archimate --out data/model/model_facts.lp
```
