"""Tests of the mxGraphModel frame check of gate 3 (pipeline.frame_errors): cell 0 without parent,
cell 1 with parent 0, every vertex and edge with parent 1. A broken frame passed the gate before and
then failed the draw.io export (parent="1" on cell 1).

  .venv/bin/python -m unittest discover tests

No LLM call. Reuses the diagram and fixture model of test_labels.py.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pipeline  # noqa: E402
from test_labels import EDGES, FIXTURE, VERTICES, drawio  # noqa: E402

FRAME = '<mxCell id="0"/><mxCell id="1" parent="0"/>'


class Frame(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run)
        patcher = mock.patch.object(pipeline, "MODEL_FACTS", FIXTURE)
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.run / "1_filter.lp").write_text("".join(f'keep_element("{e}").\n' for e in VERTICES) +
                                              "".join(f'keep_relation("{r}").\n' for r in EDGES))
        (self.run / "2_layout.lp").write_text("".join(f'band("{e}", application).\n' for e in VERTICES))

    def gate3(self, *replacements: tuple) -> list:
        """Gate 3 on the label test diagram after the given (old, new) text replacements."""
        xml = drawio(VERTICES, EDGES)
        for old, new in replacements:
            self.assertIn(old, xml)
            xml = xml.replace(old, new, 1)
        (self.run / "3_view.drawio").write_text(xml, encoding="utf-8")
        with mock.patch("sys.stdout"):
            code = pipeline.check(3, self.run)
        self.assertIn(code, (0, 1))
        result = json.loads((self.run / "3_check.json").read_text(encoding="utf-8"))
        return [(v["rule"], [i["id"] for i in v["ids"]]) for v in result["violations"]]

    def test_correct_frame_passes(self):
        self.assertEqual(self.gate3(), [])

    def test_layer_is_its_own_parent(self):
        self.assertEqual(self.gate3((FRAME, '<mxCell id="0"/><mxCell id="1" parent="1"/>')),
                         [("XML-FORMAT", ['cell "1" has parent "1", expected "0"'])])

    def test_root_with_parent_and_missing_layer(self):
        self.assertEqual(self.gate3((FRAME, '<mxCell id="0" parent="0"/>')),
                         [("XML-FORMAT", ['cell "0" has parent "0", expected none', 'cell "1" is missing'])])

    def test_vertex_and_edge_not_on_the_layer(self):
        found = self.gate3(('vertex="1" parent="1"><mxGeometry x="260"', 'vertex="1" parent="e1"><mxGeometry x="260"'),
                           ('edge="1" parent="1" source="e2"', 'edge="1" parent="0" source="e2"'))
        self.assertEqual(found, [("XML-FORMAT", ['cell "e2" has parent "e1", expected "1"',
                                                 'cell "r_plain" has parent "0", expected "1"'])])

    def test_edge_label_cell_is_allowed(self):
        child = ('<mxCell id="lbl" value="feeds" style="edgeLabel;html=1;" vertex="1" connectable="0" '
                 'parent="r_spec"><mxGeometry relative="1" as="geometry"/></mxCell>')
        self.assertEqual(self.gate3(("</root>", child + "</root>")), [])


if __name__ == "__main__":
    unittest.main()
