#!/usr/bin/env python3
"""Deterministic orchestrator of the view pipeline. No LLM decides control flow.

  run.py intents/<file>.md [--model M] [--filter M] [--layout M] [--drawio M]

M: haiku | sonnet | opus or a full model id. --model sets filter, layout and drawio, --filter,
--layout and --drawio one of them; everything else (judge, limits, effort) is pipeline.toml.
The run folder is runs/P/<timestamp>-<intent>-<setup>/, setup naming the models (setup_label).

filter -> gate 1 -> layout -> gate 2 -> drawio -> gate 3 -> render -> judge, with the repair and
judge-round limits of pipeline.toml. After gate 2 passes, scripts/preview.py draws the layout
(2_preview.drawio, no LLM, not checked) and it is rendered in the background (2_preview.png) while
drawio runs; nothing downstream reads it. If the filter recognises a predefined view of the model
(use_view/1), its content is taken over 1:1 (context.view_selection) instead of a selection, and
the judge may send the run back to layout or drawio only. Agents run through the Claude Agent SDK, one fresh query()
per call. Gates and render are scripts/pipeline.py; the inputs put into the prompts are
scripts/context.py.
"""
import argparse
import asyncio
import dataclasses
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
import tomllib
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import clingo

import context
import judge_openrouter
import pipeline
import preview

ROOT = pipeline.ROOT
AGENTS = ("filter", "layout", "drawio", "judge")
STEPS = ("filter", "layout", "drawio")  # step i is checked by gate i+1
OUTPUT = {"filter": "1_filter.lp", "layout": "2_layout.lp", "drawio": "3_view.drawio", "judge": "5_judge.json"}
TOOLS = {"filter": ["Read", "Write", "Edit", "Grep"], "layout": ["Read", "Write", "Edit", "Grep"],
         "drawio": ["Read", "Write", "Edit", "Grep"], "judge": ["Read", "Write"]}
# Permission deny rules of every agent call; Read rules also block Grep. setting_sources=[] means
# .claude/settings.json does not apply to the agents, so the secrets are denied here.
DENIED = ["Read(./.env)"]
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
MODEL_USAGE_KEYS = {"inputTokens": "input_tokens", "outputTokens": "output_tokens",
                    "cacheCreationInputTokens": "cache_creation_input_tokens",
                    "cacheReadInputTokens": "cache_read_input_tokens"}
AUTH_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
PREVIEW_PNG = "2_preview.png"
OPENROUTER = "openrouter:"  # model prefix: judge through OpenRouter instead of the Agent SDK
EFFORTS = ("low", "medium", "high", "xhigh", "max")  # claude_agent_sdk EffortLevel
ALIASES = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}

# User prompts of the agent calls; the system prompt is prompts/<agent>.md (for the filter with the
# model listing of context.py appended). {context} is context.step_context: the inputs the agent
# would otherwise read first.
PROMPT_INITIAL = "Run directory: {run}\n\n{context}"
PROMPT_REPAIR = ("Run directory: {run}\n"
                 "Repair: your previous output {run}/{output} failed the gate. "
                 "Read {run}/{gate}_check.json and {run}/{output}, and fix every violation.\n\n{context}")
PROMPT_REVISION = ("Run directory: {run}\n"
                   "Revision: the judge rejected the rendered view. "
                   "Read {run}/5_judge.json and your previous output {run}/{output}, and revise it.\n\n{context}")


class RunError(Exception):
    pass


# ---------------------------------------------------------------- config

def check_auth() -> None:
    """Warn (stderr) when an auth variable overrides the subscription login."""
    found = sorted(k for k in os.environ if k in AUTH_VARS or k.startswith("CLAUDE_CODE_USE_"))
    if found:
        print(f"WARNING: {', '.join(found)} set. The agent calls will NOT use the Claude subscription "
              "login: they are billed to that API key or cloud provider instead. Unset it to use the "
              "subscription.", file=sys.stderr, flush=True)


def load_config(path: Path, overrides: dict | None = None) -> dict:
    """pipeline.toml, with the models of overrides ({agent: alias or model id}) put in place."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    models = dict(cfg["models"]) | {a: ALIASES.get(m, m) for a, m in (overrides or {}).items() if m}
    missing = [a for a in AGENTS if a not in models]
    if missing:
        raise RunError(f"no model configured for: {', '.join(missing)}")
    tool_agents = [a for a in STEPS if models[a].startswith(OPENROUTER)]
    if tool_agents:
        raise RunError(f"{OPENROUTER} works only for the judge (it has no tools), not for: {', '.join(tool_agents)}")
    effort = dict(cfg.get("effort", {}))  # optional; an agent left out runs at the model's default
    unknown = [a for a in effort if a not in AGENTS]
    if unknown:
        raise RunError(f"[effort]: unknown agent: {', '.join(unknown)}")
    bad = [f"{a} = {v!r}" for a, v in effort.items() if v not in EFFORTS]
    if bad:
        raise RunError(f"[effort]: {', '.join(bad)}; allowed: {', '.join(EFFORTS)}")
    return {"limits": dict(cfg["limits"]), "models": models, "effort": effort}


def setup_label(models: dict) -> str:
    """Name of the step models: "sonnet" if all three agree, "sonnet-drawio-haiku" if one differs,
    else every agent with its model."""
    alias = {m: a for a, m in ALIASES.items()}
    names = {a: alias.get(models[a], models[a]).replace("/", "_") for a in STEPS}
    for base in dict.fromkeys(names.values()):
        odd = [a for a in STEPS if names[a] != base]
        if len(odd) <= 1:
            return base + "".join(f"-{a}-{names[a]}" for a in odd)
    return "-".join(f"{a}-{names[a]}" for a in STEPS)


# ---------------------------------------------------------------- agent call (SDK)

def to_jsonable(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {"_type": type(obj).__name__, **{k: to_jsonable(v) for k, v in vars(obj).items()}}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return repr(obj)


def call_agent(agent: str, model: str, prompt: str, run: Path, log_path: Path, system_prompt: Path,
               effort: str | None) -> dict:
    """One fresh query() for one agent with the system prompt file system_prompt, at the reasoning
    effort effort (None: the model's default). Writes the raw message stream to log_path.

    Returns text, usage (result message), model_usage (per model, snake_case), models (seen in
    assistant messages), num_turns, duration_ms, subtype, is_error, session_id, error."""
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, HookMatcher, ResultMessage,
                                  query)

    allowed = (run / OUTPUT[agent]).resolve()

    async def only_own_output(input_data, tool_use_id, context):
        path = input_data.get("tool_input", {}).get("file_path", "")
        if (ROOT / path).resolve() == allowed:  # ROOT / absolute path = absolute path
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": f"You may write only {allowed.relative_to(ROOT)}."}}

    options = ClaudeAgentOptions(
        system_prompt={"type": "file", "path": str(system_prompt)},
        tools=TOOLS[agent],
        allowed_tools=TOOLS[agent],
        disallowed_tools=DENIED,
        permission_mode="dontAsk",
        hooks={"PreToolUse": [HookMatcher(matcher="Write|Edit", hooks=[only_own_output])]},
        model=model,
        effort=effort,
        cwd=str(ROOT),
        setting_sources=[],  # no user/project settings, no CLAUDE.md
        strict_mcp_config=True,  # no MCP servers (also not the claude.ai connectors of the login)
        env={"ENABLE_CLAUDEAI_MCP_SERVERS": "false"},
    )
    out = {"text": None, "usage": None, "model_usage": None, "models": [], "num_turns": None,
           "duration_ms": None, "subtype": None, "is_error": True, "session_id": None, "error": None}
    models = set()

    async def go():
        with open(log_path, "w", encoding="utf-8") as log:
            async for msg in query(prompt=prompt, options=options):
                log.write(json.dumps({"ts": datetime.now().isoformat(), **to_jsonable(msg)},
                                     ensure_ascii=False) + "\n")
                if isinstance(msg, AssistantMessage):
                    models.add(msg.model)
                elif isinstance(msg, ResultMessage):
                    out.update(text=msg.result, num_turns=msg.num_turns, duration_ms=msg.duration_ms,
                               subtype=msg.subtype, is_error=msg.is_error, session_id=msg.session_id,
                               usage={k: (msg.usage or {}).get(k, 0) for k in USAGE_KEYS},
                               model_usage={m: {new: u.get(old, 0) for old, new in MODEL_USAGE_KEYS.items()}
                                            for m, u in (msg.model_usage or {}).items()})
                    if msg.errors:
                        out["error"] = "; ".join(msg.errors)

    try:
        asyncio.run(go())
    except Exception as e:  # noqa: BLE001 - logged and turned into a run error by the caller
        out["error"] = f"{type(e).__name__}: {e}"
        out["is_error"] = True
    out["models"] = sorted(models)
    return out


def call(agent: str, model: str, prompt: str, run: Path, log_path: Path, system_prompt: Path,
         effort: str | None) -> dict:
    """OpenRouter for an "openrouter:" judge (effort does not apply), else the Agent SDK."""
    if model.startswith(OPENROUTER):
        return judge_openrouter.call_judge(model.removeprefix(OPENROUTER), run, log_path)
    return call_agent(agent, model, prompt, run, log_path, system_prompt, effort)


# ---------------------------------------------------------------- run

def sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


class Run:
    def __init__(self, intent: Path, config: dict):
        self.intent, self.config = intent, config
        self.setup = setup_label(config["models"])
        self.dir = pipeline.new_run(intent, self.setup)
        self.rel = self.dir.relative_to(ROOT).as_posix()
        (self.dir / "calls").mkdir()
        # The filter's system prompt carries the whole model; identical in every run (cacheable).
        self.system_prompts = {a: ROOT / "prompts" / f"{a}.md" for a in AGENTS}
        self.system_prompts["filter"] = self.dir / "calls" / "filter_system.md"
        self.system_prompts["filter"].write_text(
            (ROOT / "prompts/filter.md").read_text(encoding="utf-8").rstrip() + "\n\n" + context.model_listing(),
            encoding="utf-8")
        self.calls = 0
        self.attempts = {a: 0 for a in AGENTS}
        self.judge_round = 1
        self.tokens = {"per_agent": {}, "per_model": {}}
        self.preview_render = None  # background thread rendering 2_preview.png
        self.lock = threading.Lock()  # events.jsonl is written by both threads

    def event(self, kind: str, **fields) -> None:
        with self.lock, open(self.dir / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(), "event": kind, **fields},
                               ensure_ascii=False) + "\n")

    def add_tokens(self, agent: str, res: dict) -> None:
        a = self.tokens["per_agent"].setdefault(agent, dict.fromkeys(USAGE_KEYS, 0))
        for k in USAGE_KEYS:
            a[k] += (res.get("usage") or {}).get(k, 0)
        for m, u in (res.get("model_usage") or {}).items():
            t = self.tokens["per_model"].setdefault(m, dict.fromkeys(USAGE_KEYS, 0))
            for k in USAGE_KEYS:
                t[k] += u.get(k, 0)

    def agent(self, agent: str, role: str, gate: int | None = None) -> None:
        output = self.dir / OUTPUT[agent]
        template = {"initial": PROMPT_INITIAL, "repair": PROMPT_REPAIR, "revision": PROMPT_REVISION}[role]
        ctx = context.step_context(self.dir, agent) if agent in STEPS else ""
        prompt = template.format(run=self.rel, output=OUTPUT[agent], gate=gate, context=ctx).rstrip()
        self.calls += 1
        self.attempts[agent] += 1
        model = self.config["models"][agent]
        effort = self.config["effort"].get(agent)
        before = sha256(output)
        print(f"[{self.calls:02d}] {agent} ({role}, {model}{f', effort {effort}' if effort else ''}) ...",
              flush=True)
        res = call(agent, model, prompt, self.dir, self.dir / "calls" / f"{self.calls:02d}_{agent}.jsonl",
                   self.system_prompts[agent], effort)
        self.add_tokens(agent, res)
        self.event("agent_call", agent=agent, role=role, attempt=self.attempts[agent],
                   judge_round=self.judge_round, requested_model=model, requested_effort=effort,
                   models_used={"assistant_messages": res.get("models", []),
                                "model_usage": sorted(res.get("model_usage") or {})},
                   usage=res.get("usage"), model_usage=res.get("model_usage"),
                   num_turns=res.get("num_turns"), duration_ms=res.get("duration_ms"),
                   subtype=res.get("subtype"), is_error=res.get("is_error"),
                   session_id=res.get("session_id"), provider=res.get("provider"),
                   is_byok=res.get("is_byok"), error=res.get("error"),
                   output_changed=sha256(output) != before, prompt=prompt, text=res.get("text"))
        if res.get("error") or res.get("is_error"):
            raise RunError(f"{agent} call failed: {res.get('error') or res.get('subtype')}")
        if not output.exists():
            raise RunError(f"{agent} did not write {self.rel}/{OUTPUT[agent]}")
        if agent == "filter":
            self.take_over_view()

    def take_over_view(self) -> None:
        """A use_view of the filter: write 1_filter.lp as the model's view, every element and relation.
        An unknown view id is left to gate 1 (UNKNOWN-VIEW), which sends it back to the filter."""
        vid = context.selected_view(self.dir)
        if vid and vid in context.load_model()["views"]:
            (self.dir / OUTPUT["filter"]).write_text(context.view_selection(self.dir, vid), encoding="utf-8")
            self.event("view_selected", view=vid, judge_round=self.judge_round)
            print(f"     predefined view {vid}: taken over 1:1 from the model", flush=True)

    def gate(self, n: int) -> bool:
        code = pipeline.check(n, self.dir)
        if code == 2:
            raise RunError(f"gate {n}: tool error")
        result = json.loads((self.dir / f"{n}_check.json").read_text(encoding="utf-8"))
        self.event("gate_check", gate=n, attempt=result["attempt"], passed=result["passed"],
                   violations=sorted({v["rule"] for v in result["violations"]}))
        return code == 0

    def preview(self) -> None:
        """Write 2_preview.drawio from the passed layout and render it in the background. A failure is
        logged and printed, never a run error: the preview is not part of the pipeline's result."""
        self.wait_preview()
        for old in (preview.OUTPUT, PREVIEW_PNG):  # keep the previews of earlier layouts
            if (self.dir / old).exists():
                pipeline.archive(self.dir, self.dir / old)
                (self.dir / old).unlink()
        judge_round, start = self.judge_round, time.monotonic()
        try:
            src = preview.write(self.dir)
        except Exception as e:  # noqa: BLE001 - see docstring
            self.preview_done(judge_round, start, f"{type(e).__name__}: {e}")
            return

        def render():
            try:
                error = pipeline.export_png(src, self.dir / PREVIEW_PNG)
            except Exception as e:  # noqa: BLE001 - see docstring
                error = f"{type(e).__name__}: {e}"
            self.preview_done(judge_round, start, error)

        self.preview_render = threading.Thread(target=render, daemon=True)
        self.preview_render.start()

    def preview_done(self, judge_round: int, start: float, error: str | None) -> None:
        self.event("preview", judge_round=judge_round, duration_ms=round((time.monotonic() - start) * 1000),
                   error=error)
        print(f"     preview failed: {error}" if error else f"     preview: {self.rel}/{PREVIEW_PNG}", flush=True)

    def wait_preview(self) -> None:
        if self.preview_render:
            self.preview_render.join()
            self.preview_render = None

    def judge(self) -> dict:
        self.agent("judge", "initial")
        try:
            verdict = json.loads((self.dir / OUTPUT["judge"]).read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise RunError(f"5_judge.json is not valid JSON: {e}")
        targets = STEPS[1:] if context.selected_view(self.dir) else STEPS  # a predefined view's content is fixed
        ok = (isinstance(verdict, dict)
              and (verdict.get("verdict"), verdict.get("target")) in
              [("pass", None)] + [("fail", t) for t in targets])
        if not ok:
            raise RunError("5_judge.json: verdict must be pass/fail, target null iff pass, "
                           f"else {'/'.join(targets)}")
        self.event("judge_verdict", judge_round=self.judge_round, verdict=verdict["verdict"],
                   target=verdict["target"])
        return verdict

    def pipeline(self) -> str:
        limits = self.config["limits"]
        start, revise = 0, False
        while True:
            for i in range(start, len(STEPS)):
                step, n = STEPS[i], i + 1
                self.agent(step, "revision" if revise and i == start else "initial")
                repairs = 0
                while not self.gate(n):
                    if repairs == limits["max_repairs"]:
                        return f"stopped: gate {n} did not pass"
                    repairs += 1
                    self.agent(step, "repair", gate=n)
                if step == "layout":
                    self.preview()
            if pipeline.render(self.dir) != 0:
                raise RunError("render failed")
            self.event("render", judge_round=self.judge_round)
            verdict = self.judge()
            if verdict["verdict"] == "pass":
                return "accepted by the judge"
            if self.judge_round == limits["max_judge_rounds"]:
                return "stopped: judge round limit"
            self.judge_round += 1
            start, revise = STEPS.index(verdict["target"]), True

    def execute(self) -> str:
        try:
            outcome = self.pipeline()
        except RunError as e:
            outcome = f"error: {e}"
        self.wait_preview()
        self.event("run_end", outcome=outcome)
        self.write_run_json(outcome)
        return outcome

    def write_run_json(self, outcome: str) -> None:
        def git(*args):
            p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
            return p.stdout.strip() if p.returncode == 0 else None

        files = [p for d in ("asp", "data", "prompts") for p in sorted((ROOT / d).rglob("*")) if p.is_file()]
        totals = dict.fromkeys(USAGE_KEYS, 0)
        for a in self.tokens["per_agent"].values():
            for k in USAGE_KEYS:
                totals[k] += a[k]
        info = {
            "intent": self.intent.resolve().relative_to(ROOT).as_posix()
            if self.intent.resolve().is_relative_to(ROOT) else str(self.intent),
            "outcome": outcome,
            "setup": self.setup,
            "view": context.selected_view(self.dir) if (self.dir / OUTPUT["filter"]).exists() else None,
            "config": self.config,
            "agent_calls": self.calls,
            "judge_rounds": self.judge_round,
            "tokens": {"total": totals, **self.tokens},
            "versions": {"claude-agent-sdk": version("claude-agent-sdk"), "clingo": clingo.__version__,
                         "python": platform.python_version()},
            "git": {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))},
            "sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in files}
            | {"intent": sha256(self.intent)},
        }
        (self.dir / "run.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("intent", type=Path)
    ap.add_argument("--model", help="model of filter, layout and drawio (haiku | sonnet | opus or a model id)")
    for a in STEPS:
        ap.add_argument(f"--{a}", help=f"model of {a}, over --model")
    args = ap.parse_args(argv)
    overrides = {a: getattr(args, a) or args.model for a in STEPS}
    try:
        check_auth()
        config = load_config(ROOT / "pipeline.toml", overrides)
    except RunError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if config["models"]["judge"].startswith(OPENROUTER) and not judge_openrouter.api_key():
        print("error: the judge runs on OpenRouter but OPENROUTER_API_KEY is not set (environment or .env)",
              file=sys.stderr)
        return 2
    if not args.intent.is_file():
        print(f"error: {args.intent} does not exist", file=sys.stderr)
        return 2
    try:
        context.check_model()
    except (context.ModelError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    run = Run(args.intent, config)
    outcome = run.execute()
    print(f"\noutcome: {outcome}\nrun: {run.rel}")
    return 0 if outcome == "accepted by the judge" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
