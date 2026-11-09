"""Inputs the agents get in their prompts instead of reading them with tools, imported by run.py.

  model_listing()     the whole model, names joined to ids, and the catalogue of the predefined
                      views (appended to the filter's system prompt)
  step_context(run, agent)  intent, kept elements and relations, (layout) the nesting of a
                      predefined view, and (drawio) the layout, for the user message of filter,
                      layout and drawio
  selected_view(run)  the predefined view RUN/1_filter.lp takes over (use_view/1), or None
  view_selection(run, v)  the text of 1_filter.lp for a predefined view: all its elements and relations

Saves the agents the Read/Grep turns over data/model/model_facts.lp. Same content as the facts,
only joined and sorted; the facts file stays the source of truth (gates read it, agents may Grep it).
"""
import re
from pathlib import Path

import pipeline

LAYERS = pipeline.ASP_DIR / "common/archimate_layers.lp"
BAND_ORDER = ("motivation", "business", "application", "technology", "other")
FACT = re.compile(r'^(\w+)\((.*)\)\.\s*$')
STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')


def unquote(s: str) -> str:
    return re.sub(r'\\(.)', r'\1', s)


def load_model(path: Path | None = None) -> dict:
    """model_facts.lp as dicts: elements {id: (type, name)}, relations {id: (type, source, target)},
    and per id the lists spec, access (access_type), plus the set directed;
    views {view id: {name, documentation, elements, relations, inside [(element, container)]}}."""
    m = {"elements": {}, "relations": {}, "spec": {}, "access": {}, "directed": set(), "views": {}}
    for line in (path or pipeline.MODEL_FACTS).read_text(encoding="utf-8").splitlines():
        f = FACT.match(line)
        if not f:
            continue
        pred, args = f.group(1), [unquote(a) for a in STRING.findall(f.group(2))]
        if pred == "element":
            m["elements"][args[0]] = (args[1], args[2])
        elif pred == "relation":
            m["relations"][args[0]] = (args[1], args[2], args[3])
        elif pred in ("specialization", "rel_specialization"):
            m["spec"].setdefault(args[0], []).append(args[1])
        elif pred == "access_type":
            m["access"].setdefault(args[0], []).append(args[1])
        elif pred == "directed":
            m["directed"].add(args[0])
        elif pred == "view":
            m["views"][args[0]] = {"name": args[1], "documentation": "", "elements": [], "relations": [], "inside": []}
        elif pred == "view_documentation":
            m["views"][args[0]]["documentation"] = args[1]
        elif pred in ("view_element", "view_relation"):
            m["views"][args[0]][pred.removeprefix("view_") + "s"].append(args[1])
        elif pred == "view_inside":
            m["views"][args[0]]["inside"].append((args[1], args[2]))
    return m


def type_bands() -> dict:
    """ArchiMate element type -> band, from asp/common/archimate_layers.lp."""
    return dict(re.findall(r'type_band\("(\w+)",\s*(\w+)\)', LAYERS.read_text(encoding="utf-8")))


def cell(s: str) -> str:
    return s.replace("|", "\\|")


def element_key(m: dict, bands: dict):
    def key(eid):
        etype, name = m["elements"][eid]
        band = bands.get(etype, "other")
        return BAND_ORDER.index(band) if band in BAND_ORDER else len(BAND_ORDER), etype, name
    return key


class ModelError(Exception):
    """The model cannot be given to the agents as it is."""


def check_model(m: dict | None = None) -> None:
    """The listings name relation endpoints by element name, so the names must be unique."""
    m = m or load_model()
    names = {}
    for eid, (_, ename) in m["elements"].items():
        names.setdefault(ename, []).append(eid)
    dup = {n: ids for n, ids in names.items() if len(ids) > 1}
    if dup:
        shown = "; ".join(f"{n!r}: {', '.join(ids)}" for n, ids in sorted(dup.items())[:10])
        raise ModelError(f"{len(dup)} element name(s) are not unique, rename them in the model ({shown})")


def relation_attrs(m: dict, rid: str) -> str:
    return ", ".join([f"access_type {a}" for a in m["access"].get(rid, [])]
                     + (["directed"] if rid in m["directed"] else []))


def model_listing() -> str:
    """Every element and relation of the model; relations sorted by source, endpoints by name."""
    m, bands = load_model(), type_bands()
    name = {eid: n for eid, (_, n) in m["elements"].items()}
    lines = ["## The model", "",
             f"The whole of `{pipeline.MODEL_FACTS.relative_to(pipeline.ROOT).as_posix()}`, joined for reading: "
             f"{len(m['elements'])} elements, {len(m['relations'])} relations. Element names are unique, "
             "so relation endpoints are given by name.", "",
             "### Elements (by band, type, name)", "",
             "| Id | Type | Specialization | Name |", "|---|---|---|---|"]
    for eid in sorted(m["elements"], key=element_key(m, bands)):
        etype, ename = m["elements"][eid]
        lines.append(f"| {eid} | {etype} | {cell(', '.join(m['spec'].get(eid, [])))} | {cell(ename)} |")
    lines += ["", "### Relations (by source name, type, target name)", "",
              "| Id | Type | Specialization | Source | Target | Attributes |", "|---|---|---|---|---|---|"]
    for rid in sorted(m["relations"], key=lambda r: (name.get(m["relations"][r][1], ""), m["relations"][r][0],
                                                     name.get(m["relations"][r][2], ""))):
        rtype, src, tgt = m["relations"][rid]
        lines.append(f"| {rid} | {rtype} | {cell(', '.join(m['spec'].get(rid, [])))} | {cell(name.get(src, src))} "
                     f"| {cell(name.get(tgt, tgt))} | {relation_attrs(m, rid)} |")
    lines += ["", "### Predefined views", "",
              "The diagrams of the model, with their documentation and size. `use_view` takes one over as "
              "it is (see the instructions).", "",
              "| View | Name | Documentation | Size |", "|---|---|---|---|"]
    for vid, v in sorted(m["views"].items(), key=lambda kv: kv[1]["name"]):
        lines.append(f"| {vid} | {cell(v['name'])} | {cell(v['documentation'])} "
                     f"| {len(v['elements'])} elements, {len(v['relations'])} relations |")
    return "\n".join(lines) + "\n"


def selected_view(run: Path) -> str | None:
    found = re.findall(r'^\s*use_view\("([^"]+)"\)', (run / "1_filter.lp").read_text(encoding="utf-8"), re.M)
    return found[0] if found else None


def view_selection(run: Path, vid: str) -> str:
    """1_filter.lp of a predefined view: use_view plus every element and relation of the view, with
    the comments the filter writes. Keeps the comment lines of the filter's own RUN/1_filter.lp (why
    the intent asks for this view). Elements by band, type and name; relations by model order."""
    m, bands = load_model(), type_bands()
    v = m["views"][vid]
    name = {eid: n for eid, (_, n) in m["elements"].items()}
    own = run / "1_filter.lp"
    reason = [l.strip() for l in own.read_text(encoding="utf-8").splitlines()
              if l.strip().startswith("%")] if own.exists() else []
    lines = [f"% Predefined view {v['name']}: taken over 1:1 from the model by run.py "
             f"({len(v['elements'])} elements, {len(v['relations'])} relations).",
             *reason, f'use_view("{vid}").', ""]
    for eid in sorted(v["elements"], key=element_key(m, bands)):
        etype, ename = m["elements"][eid]
        lines += [f"% {etype}: {ename}", f'keep_element("{eid}").']
    lines.append("")
    for rid in sorted(v["relations"], key=list(m["relations"]).index):
        rtype, src, tgt = m["relations"][rid]
        lines += [f"% {rtype}: {name.get(src, src)} -> {name.get(tgt, tgt)}", f'keep_relation("{rid}").']
    return "\n".join(lines) + "\n"


def view_nesting(vid: str) -> str:
    """Layout context of a predefined view: how the model's own view nests its elements, with a note
    where the layout rules do not allow the same nesting."""
    m, tb = load_model(), type_bands()
    v = m["views"][vid]
    name = {eid: n for eid, (_, n) in m["elements"].items()}
    band = {e: tb.get(m["elements"][e][0], "other") for e in v["elements"] if e in m["elements"]}
    containers = {}
    for e, c in v["inside"]:
        containers.setdefault(e, []).append(c)

    def content_bands(c, seen=()):  # bands of everything (transitively) nested in c on the view
        out = set()
        for e, cc in v["inside"]:
            if cc == c and e not in seen:
                out |= {band.get(e)} - {"other"} | content_bands(e, seen + (c,))
        return out

    def note(e, c):
        if len(containers[e]) > 1:
            return f"drawn {len(containers[e])} times on the model's diagram; here once: in at most one container"
        if band.get(c) != "other" and band.get(e) != band.get(c):
            return "not possible (across bands): side by side, the relation is an edge"
        if band.get(c) == "other" and len(content_bands(c)) > 1:
            return (f"the container holds elements of several bands ({', '.join(sorted(content_bands(c)))}): "
                    "only the elements of one band can stay inside it")
        return ""

    lines = [f"## Predefined view {vid}", "",
             f"`RUN/1_filter.lp` is the model's view {cell(v['name'])}, taken over 1:1. "
             + (f"In the model's own diagram these elements are nested ({len(v['inside'])}): reproduce "
                "each nesting with `inside` where the layout rules allow it (see the notes); where they do "
                "not, place the two side by side, and the relation is drawn as an edge."
                if v["inside"] else "The model's own diagram nests no elements."), ""]
    if v["inside"]:
        lines += ["| Element | Inside container | Note |", "|---|---|---|"]
        lines += [f"| {e} ({cell(name.get(e, '?'))}) | {c} ({cell(name.get(c, '?'))}) | {note(e, c)} |"
                  for e, c in v["inside"]]
    return "\n".join(lines) + "\n"


def kept(run: Path) -> tuple[list, list]:
    text = (run / "1_filter.lp").read_text(encoding="utf-8")
    return (re.findall(r'^\s*keep_element\("([^"]+)"\)', text, re.M),
            re.findall(r'^\s*keep_relation\("([^"]+)"\)', text, re.M))


def kept_listing(run: Path) -> str:
    """Kept elements and relations of RUN/1_filter.lp with their model facts and element bands."""
    m, bands = load_model(), type_bands()
    elements, relations = kept(run)
    name = {eid: n for eid, (_, n) in m["elements"].items()}
    lines = [f"## Kept elements and relations ({len(elements)} elements, {len(relations)} relations)", "",
             "`RUN/1_filter.lp` joined with `model_facts.lp`. Band: the band the element's type belongs to.", "",
             "| Id | Type | Specialization | Name | Band |", "|---|---|---|---|---|"]
    for eid in sorted(elements, key=lambda e: element_key(m, bands)(e) if e in m["elements"] else (99, "", e)):
        etype, ename = m["elements"].get(eid, ("?", "?"))
        lines.append(f"| {eid} | {etype} | {cell(', '.join(m['spec'].get(eid, [])))} | {cell(ename)} "
                     f"| {bands.get(etype, 'other')} |")
    lines += ["", "| Id | Type | Specialization | Source | Target | Attributes |", "|---|---|---|---|---|---|"]
    for rid in relations:
        rtype, src, tgt = m["relations"].get(rid, ("?", "?", "?"))
        lines.append(f"| {rid} | {rtype} | {cell(', '.join(m['spec'].get(rid, [])))} "
                     f"| {src} ({cell(name.get(src, '?'))}) | {tgt} ({cell(name.get(tgt, '?'))}) "
                     f"| {relation_attrs(m, rid)} |")
    return "\n".join(lines) + "\n"


def file_section(run: Path, name: str, lang: str = "") -> str:
    return f"## RUN/{name}\n\n```{lang}\n{(run / name).read_text(encoding='utf-8').rstrip()}\n```\n"


def step_context(run: Path, agent: str) -> str:
    """User-message context of an agent call: what the agent would otherwise read first."""
    parts = [file_section(run, "intent.md", "markdown")]
    if agent in ("layout", "drawio"):
        parts.append(kept_listing(run))
    if agent == "layout" and (vid := selected_view(run)):
        parts.append(view_nesting(vid))
    if agent == "drawio":
        parts.append(file_section(run, "2_layout.lp", "prolog"))
    return "\n".join(parts)
