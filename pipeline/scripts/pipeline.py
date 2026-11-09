"""Deterministic part of the view pipeline, imported by scripts/run.py; agents never call it.

  new_run(intent, setup)  create runs/P/<timestamp>-<intent>-<setup>/ with intent.md
  check(gate, run)   run gate 1, 2 or 3; 0 = pass, 1 = rule violations, 2 = tool error
  render(run)        3_view.drawio -> 4_render.png with the draw.io desktop CLI
  export_png(src, dst)  one .drawio -> .png export (render, and the preview of run.py)

A gate loads the model facts, the earlier step outputs, the checked agent output, every .lp file
in asp/common/ (ArchiMate tables shared by the gates) and every .lp file in asp/gate<N>/. Rules
report `violation(Code, Ids)` and explain codes with `message(Code, Text)`.
"""
import html
import json
import re
import shutil
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import clingo

ROOT = Path(__file__).resolve().parent.parent
MODEL_FACTS = ROOT / "data/model/model_facts.lp"
ASP_DIR = ROOT / "asp"

# gate -> (checked agent output, earlier outputs loaded as context, predicates the agent may write)
GATES = {
    1: ("1_filter.lp", [], {"keep_element", "keep_relation", "use_view"}),
    2: ("2_layout.lp", ["1_filter.lp"], {"band", "left_of", "above", "inside"}),
    3: ("3_view.drawio", ["1_filter.lp", "2_layout.lp"], None),
}

# Edge style keys that carry the ArchiMate relation notation (checked by asp/gate3/notation.lp).
NOTATION_KEYS = {"startArrow", "endArrow", "startFill", "endFill", "dashed", "dashPattern"}
# Vertex style keys passed to the gate (element colours: asp/gate3/colors.lp, frames: bands.lp).
VERTEX_STYLE_KEYS = {"fillColor", "strokeColor", "dashed"}

FACT_LINE = re.compile(r'^(\w+)\(\s*((?:"[^"\\]*"|[a-z]\w*)(?:\s*,\s*(?:"[^"\\]*"|[a-z]\w*))*)\s*\)\.\s*(%.*)?$')


def new_run(intent: Path, setup: str) -> Path:
    run = ROOT / "runs" / "P" / f"{datetime.now():%Y%m%d-%H%M%S}-{intent.stem}-{setup}"
    run.mkdir(parents=True)
    shutil.copy(intent, run / "intent.md")
    return run


def fact_syntax(path: Path, allowed: set) -> list:
    """Agent output may only contain one allowed fact per line, so it cannot change the check logic."""
    found = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("%"):
            continue
        m = FACT_LINE.match(line)
        if not m or m.group(1) not in allowed:
            found.append(("SYNTAX", [f"line {n}: {line[:120]}"]))
    return found


def q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def style_items(cell, keys: set) -> list:
    """(key, value) pairs of the cell style for the given keys, whitespace normalised."""
    pairs = (part.partition("=") for part in (cell.get("style") or "").split(";"))
    return [(k.strip(), " ".join(v.split())) for k, _, v in pairs if k.strip() in keys]


def label_lines(value: str) -> list:
    """Visible lines of an html label: split at <br>, <div>, <p> and newlines; tags removed, entities
    decoded, Unicode NFC, whitespace normalised; empty lines dropped."""
    parts = re.split(r"<br\s*/?>|</?(?:div|p)\b[^>]*>|\n", value or "", flags=re.I)
    lines = (" ".join(unicodedata.normalize("NFC", html.unescape(re.sub(r"<[^>]+>", "", p))).split()) for p in parts)
    return [line for line in lines if line]


def label_text(value: str) -> str:
    """Visible text of an html label on one line (lines joined with a space)."""
    return " ".join(label_lines(value))


def frame_errors(cells: list) -> list:
    """The mxGraphModel frame draw.io needs to open the file: cell 0 without parent, cell 1 with
    parent 0, every vertex and edge with parent 1 (except edge label cells, children of an edge)."""
    by_id, errors = {c.get("id"): c for c in cells}, []
    for cid, expected in (("0", None), ("1", "0")):
        if cid not in by_id:
            errors.append(f'cell "{cid}" is missing')
        elif by_id[cid].get("parent") != expected:
            errors.append(f'cell "{cid}" has parent "{by_id[cid].get("parent")}", expected '
                          + (f'"{expected}"' if expected else "none"))
    for c in cells:
        cid, parent = c.get("id"), c.get("parent")
        if cid in ("0", "1") or (c.get("vertex") != "1" and c.get("edge") != "1") or parent == "1":
            continue
        if c.get("vertex") == "1" and by_id.get(parent) is not None and by_id[parent].get("edge") == "1":
            continue  # edge label
        errors.append(f'cell "{cid}" has parent "{parent}", expected "1"')
    return errors


def drawio_facts(path: Path) -> tuple[str, list]:
    """Parse drawio XML into cell/5, cell_label/2, cell_line/3, cell_style/3, edge/3, edge_label/2,
    edge_style/3 and duplicate_id/1 facts (absolute integer coordinates; label text as in label_lines;
    styles only for VERTEX_STYLE_KEYS and NOTATION_KEYS, as written in the style)."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return "", [("XML-PARSE", [str(e)])]
    cells = root.findall(".//mxGraphModel/root/mxCell") if root.tag != "mxGraphModel" else root.findall("./root/mxCell")
    if not cells:
        return "", [("XML-FORMAT", ["no uncompressed <mxGraphModel><root><mxCell> content found"])]
    frame = frame_errors(cells)
    if frame:
        return "", [("XML-FORMAT", frame)]
    by_id, facts, seen = {c.get("id"): c for c in cells}, [], set()

    def origin(cell):  # absolute top-left corner of a vertex, following parent vertices
        g = cell.find("mxGeometry")
        x, y = float(g.get("x", 0)) if g is not None else 0, float(g.get("y", 0)) if g is not None else 0
        parent = by_id.get(cell.get("parent"))
        if parent is not None and parent.get("vertex") == "1":
            px, py = origin(parent)
            x, y = x + px, y + py
        return x, y

    for c in cells:
        cid = c.get("id")
        if c.get("vertex") != "1" and c.get("edge") != "1":
            continue
        if cid in seen:
            facts.append(f"duplicate_id({q(cid)}).")
        seen.add(cid)
        if c.get("edge") == "1":
            facts.append(f"edge({q(cid)}, {q(c.get('source', ''))}, {q(c.get('target', ''))}).")
            facts.append(f"edge_label({q(cid)}, {q(label_text(c.get('value')))}).")
            facts += [f"edge_style({q(cid)}, {q(k)}, {q(v)})." for k, v in style_items(c, NOTATION_KEYS)]
            continue
        parent = by_id.get(c.get("parent"))
        if parent is not None and parent.get("edge") == "1":
            continue  # edge label
        g = c.find("mxGeometry")
        x, y = origin(c)
        w, h = (float(g.get("width", 0)), float(g.get("height", 0))) if g is not None else (0, 0)
        facts.append(f"cell({q(cid)}, {round(x)}, {round(y)}, {round(w)}, {round(h)}).")
        facts.append(f"cell_label({q(cid)}, {q(label_text(c.get('value')))}).")
        facts += [f"cell_line({q(cid)}, {n}, {q(line)})." for n, line in enumerate(label_lines(c.get("value")), 1)]
        facts += [f"cell_style({q(cid)}, {q(k)}, {q(v.lower())})." for k, v in style_items(c, VERTEX_STYLE_KEYS)]
    return "\n".join(facts) + "\n", []


def labels() -> dict:
    """Readable label per model id, so feedback shows names next to ids."""
    text = MODEL_FACTS.read_text(encoding="utf-8")
    names = {m[0]: f"{m[2]} ({m[1]})" for m in re.findall(r'^element\("([^"]+)", "([^"]+)", "((?:[^"\\]|\\.)*)"\)\.', text, re.M)}
    rels = {}
    for rid, rtype, src, tgt in re.findall(r'^relation\("([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)"\)\.', text, re.M):
        rels[rid] = f"{rtype}: {names.get(src, src).rsplit(' (', 1)[0]} -> {names.get(tgt, tgt).rsplit(' (', 1)[0]}"
    return names | rels


def symbol_text(s: clingo.Symbol) -> list:
    if s.type == clingo.SymbolType.String:
        return [s.string]
    if s.type == clingo.SymbolType.Function and s.name == "":
        return [x for a in s.arguments for x in symbol_text(a)]
    return [str(s)]


def solve(files: list, extra: str) -> tuple[list, dict]:
    ctl = clingo.Control(["--warn=none"])
    for f in files:
        ctl.load(str(f))
    ctl.add("base", [], extra)
    ctl.ground([("base", [])])
    found, messages = [], {}
    with ctl.solve(yield_=True) as handle:
        model = next(iter(handle), None)
        if model is None:
            raise RuntimeError("the gate program is unsatisfiable (check the rules in asp/)")
        for a in model.symbols(atoms=True):
            if a.name == "violation" and len(a.arguments) == 2:
                found.append((a.arguments[0].string, symbol_text(a.arguments[1])))
            elif a.name == "message" and len(a.arguments) == 2:
                messages[a.arguments[0].string] = a.arguments[1].string
    return sorted(found), messages


def archive(run: Path, src: Path) -> int:
    """Copy src to attempts/<stem>.a<k><suffix> and return k."""
    (run / "attempts").mkdir(exist_ok=True)
    k = len(list((run / "attempts").glob(f"{src.stem}.a*{src.suffix}"))) + 1
    shutil.copy(src, run / "attempts" / f"{src.stem}.a{k}{src.suffix}")
    return k


def log(run: Path, line: str) -> None:
    with open(run / "checks.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")


def check(gate: int, run: Path) -> int:
    out_name, context, allowed = GATES[gate]
    out = run / out_name
    if not out.exists():
        print(f"error: {out} does not exist", file=sys.stderr)
        return 2
    attempt = archive(run, out)
    rule_files = sorted((ASP_DIR / f"gate{gate}").glob("*.lp"))
    if not rule_files:
        print(f"error: no rules in {ASP_DIR / f'gate{gate}'}", file=sys.stderr)
        return 2

    extra = ""
    if gate == 3:
        extra, found = drawio_facts(out)
        (run / "3_view_facts.lp").write_text(extra, encoding="utf-8")
        files = []
    else:
        found = fact_syntax(out, allowed)
        files = [out]
    messages = {"SYNTAX": "Only one fact per line with an allowed predicate is accepted (comments start with %).",
                "XML-PARSE": "The file is not well-formed XML.",
                "XML-FORMAT": "Write plain, uncompressed drawio XML: <mxfile><diagram><mxGraphModel><root>, "
                              'starting with <mxCell id="0"/><mxCell id="1" parent="0"/>, and give every vertex '
                              'and edge parent="1".'}
    if not found:
        try:
            found, rule_messages = solve([MODEL_FACTS, *[run / c for c in context], *files,
                                          *sorted((ASP_DIR / "common").glob("*.lp")), *rule_files], extra)
        except RuntimeError as e:  # clingo syntax errors in rules surface here too
            print(f"error: {e}", file=sys.stderr)
            return 2
        messages |= rule_messages

    names = labels()
    result = {
        "gate": gate, "attempt": attempt, "passed": not found,
        "violations": [{"rule": code, "message": messages.get(code, ""),
                        "ids": [{"id": i, "label": names.get(i, "")} for i in ids]} for code, ids in found],
    }
    (run / f"{gate}_check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    archive(run, run / f"{gate}_check.json")
    log(run, f"gate{gate} attempt={attempt} {'PASS' if not found else 'FAIL'} violations={len(found)}")

    print(f"gate {gate}, attempt {attempt}: {'PASS' if not found else f'FAIL ({len(found)} violations)'}")
    for v in result["violations"][:30]:
        ids = ", ".join(f"{i['id']} [{i['label']}]" if i["label"] else i["id"] for i in v["ids"])
        print(f"- {v['rule']}: {v['message']} {ids}")
    return 0 if not found else 1


def export_png(src: Path, dst: Path) -> str | None:
    """src (.drawio) -> dst (.png) with the draw.io desktop CLI; None on success, else the error."""
    exe = shutil.which("drawio")
    if not exe:
        return "draw.io desktop CLI (drawio) not found on PATH"
    cmd = [exe, "--export", "--format", "png", "--border", "20", "--output", str(dst), str(src), "--no-sandbox"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not dst.exists():
        return f"render failed\n{proc.stdout}\n{proc.stderr}"
    return None


def render(run: Path) -> int:
    for old in ("4_render.png", "5_judge.json"):  # keep earlier judge rounds
        if (run / old).exists():
            archive(run, run / old)
            (run / old).unlink()
    if error := export_png(run / "3_view.drawio", run / "4_render.png"):
        print(f"error: {error}", file=sys.stderr)
        return 2
    log(run, "render OK")
    print(run / "4_render.png")
    return 0
