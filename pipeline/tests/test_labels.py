"""Tests of the labels: gate 3 (asp/gate3/labels.lp) and the label parsing of scripts/pipeline.py.

  .venv/bin/python -m unittest discover tests

No LLM call. Fixture model: tests/fixtures/labels/model_facts.lp, three application elements (with
"&" and accents in the names), a Serving with a specialization and a Flow without one.
"""
import json
import shutil
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pipeline  # noqa: E402
from asp_tables import element_style  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/labels/model_facts.lp"

# correct labels as an agent writes them in the value attribute (XML-escaped html)
VERTICES = {
    "e1": ("Cart &amp;amp; Checkout&lt;br&gt;&lt;i&gt;ApplicationComponent&lt;/i&gt;", 20, 40),
    "e2": ("Café-Überprüfung&lt;br&gt;&lt;i&gt;ApplicationInterface&lt;/i&gt;", 260, 40),
    "e3": ("Größe prüfen&lt;br&gt;&lt;i&gt;ApplicationService&lt;/i&gt;", 500, 40),
}
EDGES = {"r_spec": ("feeds", "e1", "e2", "endArrow=open;"),
         "r_plain": ("Flow", "e2", "e3", "endArrow=block;endFill=1;dashed=1;dashPattern=6 4;")}


def drawio(vertices: dict, edges: dict, extra: str = "") -> str:
    cells = ['<mxCell id="band-application" value="Application" style="fillColor=#effafc;strokeColor=#86cddb;" '
             'vertex="1" parent="1"><mxGeometry x="0" y="0" width="700" height="120" as="geometry"/></mxCell>']
    for cid, (value, x, y) in vertices.items():
        cells.append(f'<mxCell id="{cid}" value="{value}" style="rounded=0;whiteSpace=wrap;html=1;{element_style("application")}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x}" y="{y}" width="180" height="60" as="geometry"/></mxCell>')
    for rid, (value, s, t, notation) in edges.items():
        cells.append(f'<mxCell id="{rid}" value="{value}" style="html=1;{notation}" edge="1" parent="1" '
                     f'source="{s}" target="{t}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    return ('<mxfile host="pipeline"><diagram id="view" name="View"><mxGraphModel><root>'
            '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + extra +
            "</root></mxGraphModel></diagram></mxfile>")


class Labels(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run)
        patcher = mock.patch.object(pipeline, "MODEL_FACTS", FIXTURE)
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.run / "1_filter.lp").write_text("".join(f'keep_element("{e}").\n' for e in VERTICES) +
                                              "".join(f'keep_relation("{r}").\n' for r in EDGES))
        (self.run / "2_layout.lp").write_text("".join(f'band("{e}", application).\n' for e in VERTICES))

    def gate3(self, vertices=None, edges=None, extra="") -> list:
        (self.run / "3_view.drawio").write_text(drawio(VERTICES | (vertices or {}), EDGES | (edges or {}), extra),
                                                encoding="utf-8")
        with mock.patch("sys.stdout"):
            code = pipeline.check(3, self.run)
        self.assertIn(code, (0, 1))
        result = json.loads((self.run / "3_check.json").read_text(encoding="utf-8"))
        return sorted((v["rule"], tuple(i["id"] for i in v["ids"])) for v in result["violations"])

    def test_correct_labels_pass(self):
        self.assertEqual(self.gate3(), [])

    def test_div_lines_and_decomposed_accents_pass(self):
        # draw.io's own line markup, and the name in NFD (accents as combining characters)
        nfd = unicodedata.normalize("NFD", "Café-Überprüfung")
        value = f"&lt;div&gt;{nfd}&lt;/div&gt;&lt;div&gt;&lt;i&gt;ApplicationInterface&lt;/i&gt;&lt;/div&gt;"
        self.assertEqual(self.gate3({"e2": (value, 260, 40)}), [])

    def test_renamed_element(self):
        value = "Café&lt;br&gt;&lt;i&gt;ApplicationInterface&lt;/i&gt;"
        self.assertEqual(self.gate3({"e2": (value, 260, 40)}),
                         [("LABEL-MISMATCH", ("e2", "name", "Café", "Café-Überprüfung"))])

    def test_wrong_type(self):
        value = "Größe prüfen&lt;br&gt;&lt;i&gt;ApplicationComponent&lt;/i&gt;"
        self.assertEqual(self.gate3({"e3": (value, 500, 40)}),
                         [("LABEL-MISMATCH", ("e3", "type", "ApplicationComponent", "ApplicationService"))])

    def test_name_only(self):
        self.assertEqual(self.gate3({"e3": ("Größe prüfen", 500, 40)}),
                         [("LABEL-MISMATCH", ("e3", "lines", "1", "2"))])

    def test_line_break_inside_the_name(self):
        value = "Größe&lt;br&gt;prüfen&lt;br&gt;&lt;i&gt;ApplicationService&lt;/i&gt;"
        self.assertEqual(self.gate3({"e3": (value, 500, 40)}), [
            ("LABEL-MISMATCH", ("e3", "lines", "3", "2")),
            ("LABEL-MISMATCH", ("e3", "name", "Größe", "Größe prüfen")),
            ("LABEL-MISMATCH", ("e3", "type", "prüfen", "ApplicationService")),
        ])

    def test_wrong_edge_labels(self):
        found = self.gate3(edges={"r_spec": ("Serving", "e1", "e2", "endArrow=open;"),
                                  "r_plain": ("nightly_batch", "e2", "e3", EDGES["r_plain"][3])})
        self.assertEqual(found, [("LABEL-MISMATCH", ("r_plain", "edge", "nightly_batch", "Flow")),
                                 ("LABEL-MISMATCH", ("r_spec", "edge", "Serving", "feeds"))])

    def test_edge_label_in_a_child_cell(self):
        # draw.io's separate label cell: the edge's own value is empty
        child = ('<mxCell id="lbl" value="feeds" style="edgeLabel;html=1;" vertex="1" connectable="0" '
                 'parent="r_spec"><mxGeometry relative="1" as="geometry"/></mxCell>')
        self.assertEqual(self.gate3(edges={"r_spec": ("", "e1", "e2", "endArrow=open;")}, extra=child),
                         [("LABEL-MISMATCH", ("r_spec", "edge", "", "feeds"))])


class LabelLines(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(pipeline.label_lines("A &amp; B<br/><i>T</i>"), ["A & B", "T"])
        self.assertEqual(pipeline.label_lines("<div>A</div><div><br></div><div>T</div>"), ["A", "T"])
        self.assertEqual(pipeline.label_lines("  A  B \nT"), ["A B", "T"])
        self.assertEqual(pipeline.label_text("A<br>B"), "A B")


if __name__ == "__main__":
    unittest.main()
