#!/usr/bin/env python3
"""Compact, comparable summary of one pipeline run.

  summarize_run.py <run id>        (the folder name in runs/, or a path to a run folder)

Reads run.json, events.jsonl and intent.md of the run and writes summary.json next to them.
Input tokens count cached input too (input + cache write + cache read); the cached part is
also given separately. Times are in seconds. The preview (2_preview.png) is drawn in the background
while drawio runs, so its time is listed on its own (with `at_s`, seconds from the run start) and is
not part of the wall-time split.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ("filter", "layout", "drawio", "judge")


def tokens(usage: dict) -> dict:
    cache_write = usage.get("cache_creation_input_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    return {"input": usage.get("input_tokens", 0) + cache_write + cache_read,
            "output": usage.get("output_tokens", 0),
            "cache_write": cache_write, "cache_read": cache_read}


def add(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + v for k, v in b.items()}


def summarize(run_dir: Path) -> dict:
    run = json.loads((run_dir / "run.json").read_text()) if (run_dir / "run.json").exists() else {}
    events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines() if l.strip()]
    intent = run_dir / "intent.md"

    phases = {a: {"calls": 0, "turns": 0, "time_s": 0.0, "tokens": {}} for a in AGENTS}
    gates = defaultdict(lambda: {"checks": 0, "failed": 0, "violations": 0})
    repairs = defaultdict(int)
    revisions = defaultdict(int)
    verdicts, errors, previews = [], [], []
    render_s, prev_ts, end_ts, outcome = 0.0, None, None, None

    # The run folder is named after its start time: YYYYMMDD-HHMMSS-<intent>.
    start = datetime.strptime("-".join(run_dir.name.split("-")[:2]), "%Y%m%d-%H%M%S")
    for e in events:
        ts = datetime.fromisoformat(e["ts"])
        match e["event"]:
            case "preview":  # background thread: not a step of the sequence, prev_ts stays
                previews.append({"round": e["judge_round"], "time_s": round(e["duration_ms"] / 1000, 1),
                                 "at_s": round((ts - start).total_seconds(), 1), "error": e.get("error")})
                continue
            case "agent_call":
                p = phases[e["agent"]]
                p["calls"] += 1
                p["turns"] += e.get("num_turns") or 0
                p["time_s"] += (e.get("duration_ms") or 0) / 1000
                p["tokens"] = add(p["tokens"], tokens(e.get("usage") or {}))
                if e.get("role") == "repair":
                    repairs[e["agent"]] += 1
                elif e.get("role") == "revision":
                    revisions[e["agent"]] += 1
                if e.get("is_error") or e.get("error"):
                    errors.append({"agent": e["agent"], "subtype": e.get("subtype"), "error": e.get("error")})
            case "gate_check":
                g = gates[f"gate{e['gate']}"]
                g["checks"] += 1
                g["failed"] += not e["passed"]
                g["violations"] += len(e.get("violations") or [])
            case "render":
                render_s += (ts - prev_ts).total_seconds() if prev_ts else 0
            case "judge_verdict":
                verdicts.append({"round": e["judge_round"], "verdict": e["verdict"], "target": e.get("target")})
            case "run_end":
                outcome = e["outcome"]
        prev_ts = end_ts = ts

    for p in phases.values():
        p["time_s"] = round(p["time_s"], 1)
    total_tokens = {}
    for p in phases.values():
        total_tokens = add(total_tokens, p["tokens"])
    wall_s = round((end_ts - start).total_seconds(), 1) if end_ts else None
    agents_s = round(sum(p["time_s"] for p in phases.values()), 1)

    config = run.get("config", {})
    return {
        "run_id": run_dir.name,
        "intent": {"file": run.get("intent"), "text": intent.read_text().strip() if intent.exists() else None},
        "outcome": outcome or run.get("outcome") or "unfinished",
        "view": run.get("view"),  # the predefined view taken over, or null
        "models": config.get("models"),
        "limits": config.get("limits"),
        "phases": phases,
        "total": {
            "calls": sum(p["calls"] for p in phases.values()),
            "tokens": total_tokens,
            "time_s": {"wall": wall_s, "agents": agents_s, "render": round(render_s, 1),
                       "other": round(wall_s - agents_s - render_s, 1) if wall_s is not None else None},
        },
        "iterations": {
            "judge_rounds": len(verdicts),
            "verdicts": verdicts,
            "gates": dict(sorted(gates.items())),
            "repairs": dict(repairs),
            "revisions": dict(revisions),
        },
        "previews": previews,
        "errors": errors,
        "git": run.get("git"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="run id (folder name in runs/) or path to a run folder")
    args = ap.parse_args()
    run_dir = Path(args.run) if Path(args.run).is_dir() else ROOT / "runs" / args.run
    if not (run_dir / "events.jsonl").exists():
        sys.exit(f"no events.jsonl in {run_dir}")
    summary = summarize(run_dir)
    out = run_dir / "summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
