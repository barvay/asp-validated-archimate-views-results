"""Judge through OpenRouter: one multimodal chat completion instead of an agent session.

Used by run.py when [models] judge = "openrouter:<model>", so the judge can come from another
provider than the generating agents. The inputs the Claude judge reads with tools are put into
the message; the reply is written to RUN/5_judge.json and validated by run.py.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://openrouter.ai/api/v1/chat/completions"
INPUTS = ("intent.md", "1_filter.lp", "2_layout.lp", "3_view.drawio")


def api_key() -> str | None:
    """OPENROUTER_API_KEY from the environment, else from ROOT/.env. Nothing else is read from .env."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "OPENROUTER_API_KEY" and value.strip():
                return value.strip().strip('"').strip("'")
    return None


def usage_from(u: dict) -> dict:
    """OpenRouter usage -> the four token fields of run.py. prompt_tokens includes cached tokens,
    so input_tokens is the uncached rest (as in the Anthropic usage). Output includes reasoning."""
    details = u.get("prompt_tokens_details") or {}
    read, write = details.get("cached_tokens") or 0, details.get("cache_write_tokens") or 0
    return {"input_tokens": (u.get("prompt_tokens") or 0) - read - write,
            "output_tokens": u.get("completion_tokens") or 0,
            "cache_creation_input_tokens": write, "cache_read_input_tokens": read}


def call_judge(model: str, run: Path, log_path: Path) -> dict:
    """Same return shape as run.call_agent."""
    out = {"text": None, "usage": None, "model_usage": None, "models": [], "num_turns": 1,
           "duration_ms": None, "subtype": None, "is_error": True, "session_id": None, "error": None,
           "provider": None, "is_byok": None}
    key = api_key()
    if not key:
        out["error"] = "OPENROUTER_API_KEY is not set (environment or .env)"
        return out

    parts = [{"type": "text", "text": f"## {name}\n\n{(run / name).read_text(encoding='utf-8')}"}
             for name in INPUTS if (run / name).exists()]
    png = base64.b64encode((run / "4_render.png").read_bytes()).decode()
    parts.append({"type": "text", "text": "## 4_render.png"})
    parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png}"}})
    body = {"model": model,
            "messages": [{"role": "system", "content": (ROOT / "prompts/judge_api.md").read_text(encoding="utf-8")},
                         {"role": "user", "content": parts}],
            "response_format": {"type": "json_object"},
            "provider": {"require_parameters": True}}  # OpenRouter picks the provider

    def log(kind, data):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(), "_type": kind, **data}, ensure_ascii=False) + "\n")

    logged = json.loads(json.dumps(body))
    logged["messages"][1]["content"][-1]["image_url"]["url"] = f"<4_render.png, {len(png)} base64 chars>"
    log("request", logged)

    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        out["error"] = f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        out["error"] = f"{type(e).__name__}: {e}"
    out["duration_ms"] = round((time.monotonic() - start) * 1000)
    if out["error"]:
        log("error", {"error": out["error"]})
        return out

    log("response", resp)
    choice = (resp.get("choices") or [{}])[0]
    usage = usage_from(resp.get("usage") or {})
    model_used = resp.get("model") or model
    out.update(usage=usage, model_usage={model_used: usage}, models=[model_used],
               session_id=resp.get("id"), provider=resp.get("provider"),
               is_byok=(resp.get("usage") or {}).get("is_byok"),
               subtype=choice.get("finish_reason"))
    if choice.get("error") or "error" in resp:
        out["error"] = json.dumps(choice.get("error") or resp.get("error"), ensure_ascii=False)[:500]
        return out
    if choice.get("finish_reason") != "stop":
        out["error"] = f"finish_reason {choice.get('finish_reason')}"
        return out

    text = (choice.get("message") or {}).get("content") or ""
    reply = text.strip()
    if reply.startswith("```"):  # tolerate a fenced reply; run.py validates the JSON
        reply = reply.split("\n", 1)[-1].rsplit("```", 1)[0]
    (run / "5_judge.json").write_text(reply.strip() + "\n", encoding="utf-8")
    out.update(text=text, is_error=False)
    return out
