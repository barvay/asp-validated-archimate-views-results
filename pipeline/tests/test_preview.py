"""Tests of the deterministic preview (scripts/preview.py): for layouts that pass gate 2, the preview
diagram passes gate 3 (geometry, nesting, bands, frames, colours, labels, notation).

  .venv/bin/python -m unittest discover tests

No LLM call, no draw.io export. Reuses the fixture model of test_layout.py.
"""
import json
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pipeline  # noqa: E402
import preview  # noqa: E402
from test_layout import BANDS, FIXTURE  # noqa: E402


class Preview(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run)
        patcher = mock.patch.object(pipeline, "MODEL_FACTS", FIXTURE)
        patcher.start()
        self.addCleanup(patcher.stop)

    def check(self, relations: list, *facts: str, elements=tuple(BANDS)) -> ET.Element:
        """Preview of the layout (bands of the elements plus facts such as 'left_of(a,b)'); asserts
        that gate 2 passes on the layout and gate 3 on the preview. Returns the diagram root."""
        (self.run / "1_filter.lp").write_text("".join(f'keep_element("{e}").\n' for e in elements) +
                                              "".join(f'keep_relation("{r}").\n' for r in relations))
        quoted = [f[:f.index("(") + 1] + ", ".join(f'"{x.strip()}"' for x in f[f.index("(") + 1:-1].split(",")) + ")."
                  for f in facts]
        (self.run / "2_layout.lp").write_text("".join(f'band("{e}", {BANDS[e]}).\n' for e in elements) +
                                              "\n".join(quoted) + "\n")
        with mock.patch("sys.stdout"):
            self.assertEqual(pipeline.check(2, self.run), 0, (self.run / "2_check.json").read_text())
            shutil.copy(preview.write(self.run), self.run / "3_view.drawio")
            pipeline.check(3, self.run)
        result = json.loads((self.run / "3_check.json").read_text(encoding="utf-8"))
        self.assertEqual([(v["rule"], [i["id"] for i in v["ids"]]) for v in result["violations"]], [])
        return ET.parse(self.run / preview.OUTPUT).getroot()

    def edges(self, root: ET.Element) -> set:
        return {c.get("id") for c in root.iter("mxCell") if c.get("edge") == "1"}

    def test_bands_only(self):
        root = self.check(["r_pc"])
        self.assertEqual(self.edges(root), {"r_pc"})

    def test_left_of_and_above(self):
        self.check(["r_pc", "r_ca"], "left_of(a,b)", "left_of(b,c)", "above(c,d)", "left_of(p,q)", "above(a,p)")

    def test_every_strategy_passes(self):
        self.check(["r_pc", "r_ca"], "left_of(a,b)", "left_of(b,c)", "above(c,d)", "left_of(p,q)", "above(a,p)")
        for strategy in preview.STRATEGIES:
            with self.subTest(strategy=strategy), mock.patch("sys.stdout"):
                (self.run / "3_view.drawio").write_text(preview.preview(self.run, strategy), encoding="utf-8")
                pipeline.check(3, self.run)
                result = json.loads((self.run / "3_check.json").read_text(encoding="utf-8"))
                self.assertEqual(result["violations"], [])

    def test_crossings(self):
        def box(i, x, y):
            return f'<mxCell id="{i}" vertex="1"><mxGeometry x="{x}" y="{y}" width="10" height="10"/></mxCell>'
        xml = ("<root>" + box("a", 0, 0) + box("b", 100, 100) + box("c", 100, 0) + box("d", 0, 100)
               + '<mxCell id="e1" edge="1" source="a" target="b" style=""/>'
               + '<mxCell id="e2" edge="1" source="c" target="d" style=""/></root>')
        self.assertEqual(preview.crossings(xml)[0], 1)

    def test_nesting_replaces_edges(self):
        root = self.check(["r_pa", "r_pb", "r_qp", "r_pc"], "inside(a,p)", "inside(b,p)", "inside(p,q)",
                          "left_of(a,b)", "left_of(q,c)")
        self.assertEqual(self.edges(root), {"r_pc"})

    def test_grouping_container_in_band_frame(self):
        self.check(["r_pc"], "inside(c,g)", "inside(d,g)", "left_of(c,d)", "left_of(p,g)")

    def test_loose_grouping_follows_above(self):
        """A Grouping outside every frame is placed between frames as its above facts require."""
        self.check(["r_pc"], "above(x,g)", "above(g,a)")
        self.check(["r_pc"], "above(g,x)")
        self.check(["r_pc"], "above(t,g)")


if __name__ == "__main__":
    unittest.main()
