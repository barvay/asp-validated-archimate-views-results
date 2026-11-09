"""Tests of the ArchiMate relation notation: export of the relation attributes and gate 3 (notation.lp).

  .venv/bin/python -m unittest discover tests

No LLM call. Gate 3 runs on a fixture model (tests/fixtures/notation/model_facts.lp) with one
relation per notation kind; the correct styles are read from the table in prompts/drawio.md, so the
prompt and the gate rules are tested against each other.
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import export_facts  # noqa: E402
import pipeline  # noqa: E402
from asp_tables import element_style  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/notation/model_facts.lp"
# relation id -> type, for the edge labels (the fixture relations have no specialization)
REL_TYPES = dict(re.findall(r'^relation\("([^"]+)", "([^"]+)"', FIXTURE.read_text(encoding="utf-8"), re.M))

# row of the notation table in prompts/drawio.md -> relation of the fixture model
ROWS = {
    "Composition": "r_comp", "Aggregation": "r_aggr", "Assignment": "r_assign",
    "Realization": "r_real", "Serving": "r_serv", "Triggering": "r_trig", "Flow": "r_flow",
    "Influence": "r_infl", "Specialization": "r_spec",
    "Access, `access_type` write": "r_acc_w", "Access, read": "r_acc_r",
    "Access, access": "r_acc_a", "Access, readwrite": "r_acc_rw",
    "Association with `directed(Id)`": "r_assoc_d", "Association, undirected": "r_assoc_u",
}


def prompt_notation() -> dict:
    """Relation id -> NOTATION style string, from the table in prompts/drawio.md."""
    text = (ROOT / "prompts/drawio.md").read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\s*\| (.+?) \| `([^`]*)` \|$", text, re.M))
    return {rel: rows[row] for row, rel in ROWS.items()}


def drawio(styles: dict) -> str:
    """One row of source/target pairs per relation, an edge with the given notation between them,
    all in the application band frame."""
    height = 40 + len(styles) * 120
    cells = [f'<mxCell id="band-application" value="Application" style="fillColor=#effafc;strokeColor=#86cddb;" '
             f'vertex="1" parent="1"><mxGeometry x="0" y="0" width="600" height="{height}" as="geometry"/></mxCell>']
    edges = []
    for i, (rel, notation) in enumerate(sorted(styles.items())):
        y = 40 + i * 120
        for end, x in (("s", 40), ("t", 400)):
            name = f"{rel} {'source' if end == 's' else 'target'}"
            cells.append(f'<mxCell id="{rel}_{end}" value="{name}&lt;br&gt;&lt;i&gt;ApplicationComponent&lt;/i&gt;" '
                         f'style="rounded=0;html=1;{element_style("application")}" vertex="1" parent="1">'
                         f'<mxGeometry x="{x}" y="{y}" width="160" height="60" as="geometry"/></mxCell>')
        edges.append(f'<mxCell id="{rel}" value="{REL_TYPES[rel]}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;fontSize=10;{notation}" '
                     f'edge="1" parent="1" source="{rel}_s" target="{rel}_t"><mxGeometry relative="1" as="geometry"/></mxCell>')
    return ('<mxfile host="pipeline"><diagram id="view" name="View"><mxGraphModel grid="1" gridSize="10"><root>'
            '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells + edges) +
            "</root></mxGraphModel></diagram></mxfile>")


class GateNotation(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run)
        rels = list(ROWS.values())
        (self.run / "1_filter.lp").write_text(
            "".join(f'keep_element("{r}_s").\nkeep_element("{r}_t").\nkeep_relation("{r}").\n' for r in rels))
        (self.run / "2_layout.lp").write_text(
            "".join(f'band("{r}_{e}", application).\n' for r in rels for e in "st"))
        patcher = mock.patch.object(pipeline, "MODEL_FACTS", FIXTURE)
        patcher.start()
        self.addCleanup(patcher.stop)

    def check(self, styles: dict) -> list:
        """Run gate 3; return the violations as (rule, ids) tuples."""
        (self.run / "3_view.drawio").write_text(drawio(styles), encoding="utf-8")
        with mock.patch("sys.stdout"):
            code = pipeline.check(3, self.run)
        self.assertIn(code, (0, 1))
        result = json.loads((self.run / "3_check.json").read_text(encoding="utf-8"))
        return [(v["rule"], tuple(i["id"] for i in v["ids"])) for v in result["violations"]]

    def test_prompt_table_covers_every_kind(self):
        self.assertEqual(len(prompt_notation()), len(ROWS))

    def test_prompt_table_passes(self):
        self.assertEqual(self.check(prompt_notation()), [])

    def test_plain_block_arrow_fails_except_triggering(self):
        # the drawing of the earlier pipeline version: endArrow=block on every edge
        styles = dict.fromkeys(ROWS.values(), "endArrow=block;")
        failed = {ids[0] for rule, ids in self.check(styles) if rule == "RELATION-NOTATION"}
        self.assertEqual(failed, set(ROWS.values()) - {"r_trig"})

    def test_reported_key_and_values(self):
        styles = prompt_notation() | {"r_serv": "endArrow=block;"}
        self.assertEqual(self.check(styles),
                         [("RELATION-NOTATION", ("r_serv", "endArrow", "block", "open"))])

    def test_missing_key_uses_drawio_default(self):
        # no endArrow -> draw.io draws "classic"; no dashPattern on Realization -> default "3 3"
        styles = prompt_notation() | {"r_serv": "", "r_real": "endArrow=block;endFill=0;dashed=1;"}
        self.assertEqual(self.check(styles),
                         [("RELATION-NOTATION", ("r_serv", "endArrow", "classic", "open"))])

    def test_fill_checked_only_where_it_matters(self):
        styles = prompt_notation() | {"r_serv": "endArrow=open;endFill=0;",
                                      "r_comp": "startArrow=diamondThin;startFill=0;endArrow=none;"}
        self.assertEqual(self.check(styles),
                         [("RELATION-NOTATION", ("r_comp", "startFill", "0", "1"))])

    def test_access_direction_and_dash_pattern(self):
        styles = prompt_notation() | {"r_acc_w": "startArrow=open;endArrow=none;dashed=1;dashPattern=1 4;",
                                      "r_flow": "endArrow=block;endFill=1;dashed=1;dashPattern=1 4;"}
        self.assertEqual(sorted(self.check(styles)), [
            ("RELATION-NOTATION", ("r_acc_w", "endArrow", "none", "open")),
            ("RELATION-NOTATION", ("r_acc_w", "startArrow", "open", "none")),
            ("RELATION-NOTATION", ("r_flow", "dashPattern", "1 4", "6 4")),
        ])

    def test_association_direction(self):
        styles = prompt_notation() | {"r_assoc_d": "endArrow=none;", "r_assoc_u": "endArrow=openAsync;"}
        self.assertEqual(sorted(self.check(styles)), [
            ("RELATION-NOTATION", ("r_assoc_d", "endArrow", "none", "openAsync")),
            ("RELATION-NOTATION", ("r_assoc_u", "endArrow", "openAsync", "none")),
        ])


class ExportRelationAttributes(unittest.TestCase):
    MODEL = """<?xml version="1.0" encoding="UTF-8"?>
<archimate:model xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:archimate="http://www.archimatetool.com/archimate" name="t" id="m">
  <folder name="f" id="f">
    <element xsi:type="archimate:ApplicationComponent" name="A" id="a"/>
    <element xsi:type="archimate:DataObject" name="D" id="d"/>
    <element xsi:type="archimate:AccessRelationship" id="acc_default" source="a" target="d"/>
    <element xsi:type="archimate:AccessRelationship" id="acc_read" source="a" target="d" accessType="1"/>
    <element xsi:type="archimate:AccessRelationship" id="acc_rw" source="a" target="d" accessType="3"/>
    <element xsi:type="archimate:AssociationRelationship" id="as_dir" source="a" target="d" directed="true"/>
    <element xsi:type="archimate:AssociationRelationship" id="as_undir" source="a" target="d"/>
  </folder>
</archimate:model>
"""

    def test_access_type_and_directed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.archimate"
            path.write_text(self.MODEL, encoding="utf-8")
            lines = export_facts.export(path).splitlines()
        self.assertIn('access_type("acc_default", "write").', lines)
        self.assertIn('access_type("acc_read", "read").', lines)
        self.assertIn('access_type("acc_rw", "readwrite").', lines)
        self.assertIn('directed("as_dir").', lines)
        self.assertFalse(any(line.startswith('directed("as_undir")') for line in lines))


if __name__ == "__main__":
    unittest.main()
