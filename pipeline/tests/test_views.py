"""Tests of the predefined views: export of the views (scripts/export_facts.py), the 1:1 take-over of
a use_view (context.view_selection) and gate 1 on it (asp/gate1/views.lp), and a nesting
specialization, `shown_nested` (asp/common/nesting.lp with one test fact, gates 2 and 3, preview).

  .venv/bin/python -m unittest discover tests

No LLM call. Fixture: tests/fixtures/views/model.archimate (diagram v1: a -> r connection, s and c
nested in the node n by shown_nested; diagram v2: x; r_xr on no diagram), exported to model facts per test.
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

import context  # noqa: E402
import export_facts  # noqa: E402
import pipeline  # noqa: E402
import preview  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/views/model.archimate"
VIEW_ELEMENTS = {"a", "r", "n", "s", "c"}
VIEW_RELATIONS = {"r_ar", "r_ns", "r_nc"}
BANDS = {"a": "business", "r": "business", "x": "business", "n": "technology", "s": "technology",
         "c": "application"}


class Views(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run)
        self.facts = self.run / "model_facts.lp"
        self.facts.write_text(export_facts.export(FIXTURE), encoding="utf-8")
        asp = self.run / "asp"  # the rules with one nesting specialization, as a project would add it
        shutil.copytree(pipeline.ASP_DIR, asp)
        with open(asp / "common/nesting.lp", "a", encoding="utf-8") as f:
            f.write('nesting_specialization("shown_nested").\n')
        for patcher in (mock.patch.object(pipeline, "MODEL_FACTS", self.facts),
                        mock.patch.object(pipeline, "ASP_DIR", asp),
                        mock.patch.object(preview, "NESTING_RULES", asp / "common/nesting.lp")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def gate(self, n: int) -> list:
        with mock.patch("sys.stdout"):
            code = pipeline.check(n, self.run)
        self.assertIn(code, (0, 1))
        result = json.loads((self.run / f"{n}_check.json").read_text(encoding="utf-8"))
        return [(v["rule"], [i["id"] for i in v["ids"]]) for v in result["violations"]]

    def take_over(self, vid: str = "v1") -> None:
        (self.run / "1_filter.lp").write_text(context.view_selection(self.run, vid), encoding="utf-8")

    def test_export(self):
        v = context.load_model()["views"]
        self.assertEqual(sorted(v), ["v1", "v2"])  # every diagram is a view
        self.assertEqual(v["v1"]["name"], "Test view")
        self.assertEqual(v["v1"]["documentation"], "test purpose")
        self.assertEqual(v["v2"]["documentation"], "")
        self.assertEqual(set(v["v1"]["elements"]), VIEW_ELEMENTS)
        # the connection, and the relations shown by nesting (container -> nested element)
        self.assertEqual(set(v["v1"]["relations"]), VIEW_RELATIONS)
        self.assertEqual(sorted(v["v1"]["inside"]), [("c", "n"), ("s", "n")])

    def test_catalogue_in_model_listing(self):
        with mock.patch.object(pipeline, "ROOT", self.run):  # the listing names the facts file relative to ROOT
            self.assertIn("| v1 | Test view | test purpose |", context.model_listing())

    def test_take_over_passes_gate1(self):
        self.take_over()
        self.assertEqual(context.selected_view(self.run), "v1")
        self.assertEqual(set(context.kept(self.run)[0]), VIEW_ELEMENTS)
        self.assertEqual(set(context.kept(self.run)[1]), VIEW_RELATIONS)
        self.assertEqual(self.gate(1), [])

    def test_gate1_view_mismatch(self):
        self.take_over()
        text = (self.run / "1_filter.lp").read_text(encoding="utf-8")
        text = text.replace('keep_relation("r_ns").', "") + 'keep_element("x").\nkeep_relation("r_xr").\n'
        (self.run / "1_filter.lp").write_text(text, encoding="utf-8")
        self.assertEqual(sorted(self.gate(1)), [("VIEW-EXTRA-ELEMENT", ["v1", "x"]),
                                                ("VIEW-EXTRA-RELATION", ["v1", "r_xr"]),
                                                ("VIEW-MISSING-RELATION", ["v1", "r_ns"])])

    def test_gate1_unknown_view(self):
        (self.run / "1_filter.lp").write_text('use_view("v9").\n', encoding="utf-8")
        self.assertIn(("UNKNOWN-VIEW", ["v9"]), self.gate(1))

    def layout(self, *facts: str) -> None:
        self.take_over()
        (self.run / "2_layout.lp").write_text("".join(f'band("{e}", {BANDS[e]}).\n' for e in sorted(VIEW_ELEMENTS))
                                              + "".join(f + "\n" for f in facts), encoding="utf-8")

    def test_specialization_nesting(self):
        """s in n (same band, shown_nested): nested, gate 3 wants no edge for r_ns; the preview draws none."""
        self.layout('inside("s", "n").')
        self.assertEqual(self.gate(2), [])
        shutil.copy(preview.write(self.run), self.run / "3_view.drawio")
        self.assertEqual(self.gate(3), [])
        edges = {c.get("id") for c in ET.parse(self.run / "3_view.drawio").getroot().iter("mxCell") if c.get("edge")}
        self.assertEqual(edges, {"r_ar", "r_nc"})

    def test_specialization_nesting_across_bands(self):
        """c (application) cannot be nested in n (technology): the band frames forbid it, r_nc is an edge."""
        self.layout('inside("c", "n").')
        self.assertEqual(self.gate(2), [("NESTED-ACROSS-BANDS", ["c", "n"])])

    def test_layout_context_lists_view_nesting(self):
        self.layout()
        (self.run / "intent.md").write_text("Show the test view.\n", encoding="utf-8")
        text = context.step_context(self.run, "layout")
        self.assertIn("## Predefined view v1", text)
        self.assertIn("| s (S) | n (N) |  |", text)
        self.assertIn("| c (C) | n (N) | not possible (across bands)", text)
        self.assertNotIn("Predefined view", context.step_context(self.run, "drawio"))


if __name__ == "__main__":
    unittest.main()
