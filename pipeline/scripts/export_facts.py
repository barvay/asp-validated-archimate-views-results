#!/usr/bin/env python3
"""Export an Archi model (.archimate) as ASP model facts (schema: docs/fact-schema.md).

Helper, not a pipeline step: the pipeline reads data/model/model_facts.lp as given input; this
script is how that file was produced. Rerun it when the model changes. Deterministic: facts are
sorted by id, no timestamps.

Usage: python3 scripts/export_facts.py MODEL.archimate [--out FILE]
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
NOT_CONCEPTS = {"ArchimateDiagramModel", "SketchModel", "CanvasModel"}
# Properties exported as property/3 facts. Only what a check or the filtering agent needs (none here).
EXPORTED_PROPERTIES = ()
# Archi accessType attribute -> access mode; an absent attribute is Archi's default, write.
ACCESS_TYPES = {"0": "write", "1": "read", "2": "access", "3": "readwrite"}


def q(text: str) -> str:
    """ASP string literal."""
    text = " ".join((text or "").split())
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def view_facts(view, relation_ends: dict) -> list:
    """Facts of one diagram: its elements, the relations it shows (as a connection, or by nesting:
    a relation from the container to the nested element) and its nestings."""
    v = q(view.get("id"))
    out = [f"view({v}, {q(view.get('name'))})."]
    doc = view.findtext("documentation")
    if doc and doc.strip():
        out.append(f"view_documentation({v}, {q(doc)}).")
    elements, relations, nested = set(), set(), set()

    def walk(node, container):
        for child in node.findall("child"):
            e = child.get("archimateElement")
            if e:
                elements.add(e)
                if container:
                    nested.add((e, container))
                    relations.update(r for r, ends in relation_ends.items() if ends == (container, e))
            for c in child.findall("sourceConnection"):
                if c.get("archimateRelationship"):
                    relations.add(c.get("archimateRelationship"))
            walk(child, e or container)
    walk(view, None)
    out += [f"view_element({v}, {q(e)})." for e in sorted(elements)]
    out += [f"view_relation({v}, {q(r)})." for r in sorted(relations)]
    out += [f"view_inside({v}, {q(e)}, {q(c)})." for e, c in sorted(nested)]
    return out


def export(path: Path) -> str:
    root = ET.parse(path).getroot()
    profiles = {p.get("id"): p.get("name") for p in root.iter("profile")}
    elements, relations, specs, rel_specs, props, rel_attrs = [], [], [], [], [], []
    relation_ends, diagrams = {}, []

    for node in root.iter("element"):
        kind = node.get(XSI_TYPE, "").split(":")[-1]
        if kind == "ArchimateDiagramModel":
            diagrams.append(node)
        if kind in NOT_CONCEPTS:
            continue
        cid = node.get("id")
        spec = [profiles[p] for p in (node.get("profiles") or "").split() if p in profiles]
        if kind.endswith("Relationship"):
            relation_ends[cid] = (node.get("source"), node.get("target"))
            relations.append(f"relation({q(cid)}, {q(kind[:-len('Relationship')])}, "
                             f"{q(node.get('source'))}, {q(node.get('target'))}).")
            rel_specs += [f"rel_specialization({q(cid)}, {q(s)})." for s in spec]
            if kind == "AccessRelationship":
                rel_attrs.append(f"access_type({q(cid)}, {q(ACCESS_TYPES[node.get('accessType', '0')])}).")
            if kind == "AssociationRelationship" and node.get("directed") == "true":
                rel_attrs.append(f"directed({q(cid)}).")
        else:
            elements.append(f"element({q(cid)}, {q(kind)}, {q(node.get('name'))}).")
            specs += [f"specialization({q(cid)}, {q(s)})." for s in spec]
        for p in node.findall("property"):
            if p.get("key") in EXPORTED_PROPERTIES:
                props.append(f"property({q(cid)}, {q(p.get('key'))}, {q(p.get('value'))}).")

    views = sorted((view_facts(d, relation_ends) for d in diagrams), key=lambda f: f[:1])
    name = root.get("name", path.name)
    out = [f"% Model facts exported from {path.name} (model: {name}) by scripts/export_facts.py.",
           "% Schema: docs/fact-schema.md. Ids are the Archi XML ids. Do not edit by hand.",
           f"% {len(elements)} elements, {len(relations)} relations."]
    for title, block in (("Elements", elements), ("Element specializations", specs),
                         ("Relations", relations), ("Relation specializations", rel_specs),
                         ("Relation attributes", rel_attrs),
                         ("Properties", props)):
        out += ["", f"% {title}"] + sorted(block)
    out += ["", "% Views: every diagram of the model is a predefined view"]
    for facts in views:
        out += [""] * bool(facts) + facts  # in the order of view, header, members, nesting
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--out")
    args = ap.parse_args()
    text = export(Path(args.model))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
