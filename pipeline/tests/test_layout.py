"""Tests of the gate 2 layout rules: IMPLIED-CYCLE and the frame of `other` elements.

  .venv/bin/python -m unittest discover tests

No LLM call. Fixture model: tests/fixtures/layout/model_facts.lp (x business; p, q application
containers; a, b, c, d application; t technology; g a Grouping), with the Composition/Aggregation
relations of the nestings; r_pd (p -> d) is in the model but not kept.
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

FIXTURE = ROOT / "tests/fixtures/layout/model_facts.lp"
BANDS = {"x": "business", "p": "application", "q": "application", "a": "application",
         "b": "application", "c": "application", "d": "application", "t": "technology", "g": "other"}
KEPT_RELATIONS = ["r_pa", "r_pb", "r_qb", "r_qp", "r_pg", "r_pc", "r_ca"]


class Layout(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run)
        patcher = mock.patch.object(pipeline, "MODEL_FACTS", FIXTURE)
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.run / "1_filter.lp").write_text("".join(f'keep_element("{e}").\n' for e in BANDS) +
                                              "".join(f'keep_relation("{r}").\n' for r in KEPT_RELATIONS))

    def gate2(self, *facts: str) -> list:
        """Run gate 2 on the bands of all elements plus the given facts, e.g. 'left_of(a,b)'."""
        quoted = [f[:f.index("(") + 1] + ", ".join(f'"{x.strip()}"' for x in f[f.index("(") + 1:-1].split(",")) + ")."
                  for f in facts]
        (self.run / "2_layout.lp").write_text(
            "".join(f'band("{e}", {b}).\n' for e, b in BANDS.items()) + "\n".join(quoted) + "\n")
        with mock.patch("sys.stdout"):
            code = pipeline.check(2, self.run)
        self.assertIn(code, (0, 1))
        result = json.loads((self.run / "2_check.json").read_text(encoding="utf-8"))
        return sorted((v["rule"], tuple(i["id"] for i in v["ids"])) for v in result["violations"])

    def test_valid_nested_layout_passes(self):
        self.assertEqual(self.gate2("inside(a,p)", "inside(b,p)", "left_of(a,b)", "left_of(p,c)",
                                    "above(x,p)", "above(p,t)", "inside(t,g)", "above(c,g)"), [])

    def test_inherited_on_one_side(self):
        # a is inside p, p is left of b, so a is left of b: left_of(b, a) is impossible
        self.assertEqual(self.gate2("inside(a,p)", "left_of(p,b)", "left_of(b,a)"),
                         [("IMPLIED-CYCLE", ("left_of", "b", "a")), ("IMPLIED-CYCLE", ("left_of", "p", "b"))])

    def test_inherited_on_both_sides(self):
        self.assertEqual(self.gate2("inside(a,p)", "inside(b,q)", "above(p,q)", "above(b,a)"),
                         [("IMPLIED-CYCLE", ("above", "b", "a")), ("IMPLIED-CYCLE", ("above", "p", "q"))])

    def test_chain_through_nested_containers(self):
        self.assertEqual(self.gate2("inside(a,p)", "inside(p,q)", "left_of(q,b)", "left_of(b,c)", "left_of(c,a)"),
                         [("IMPLIED-CYCLE", ("left_of", "b", "c")), ("IMPLIED-CYCLE", ("left_of", "c", "a")),
                          ("IMPLIED-CYCLE", ("left_of", "q", "b"))])

    def test_band_order_through_other_container(self):
        # g holds the technology node t, so g is in the technology frame, below the business x
        self.assertEqual(self.gate2("inside(t,g)", "above(g,x)"), [("IMPLIED-CYCLE", ("above", "g", "x"))])

    def test_band_order_of_other_nested_in_band_element(self):
        # the empty Grouping g nested in the application component p is in the application frame
        self.assertEqual(self.gate2("inside(g,p)", "above(t,g)"), [("IMPLIED-CYCLE", ("above", "t", "g"))])

    def test_plain_cycle_reported_once(self):
        self.assertEqual(self.gate2("left_of(a,b)", "left_of(b,a)"), [("CYCLE", ("left_of", "a", "b"))])

    def test_plain_band_order_reported_once(self):
        self.assertEqual(self.gate2("above(t,x)"), [("ABOVE-AGAINST-BANDS", ("t", "x"))])

    def test_against_bands_does_not_hide_other_facts(self):
        found = self.gate2("above(t,x)", "inside(a,p)", "left_of(p,b)", "left_of(b,a)")
        self.assertIn(("ABOVE-AGAINST-BANDS", ("t", "x")), found)
        self.assertIn(("IMPLIED-CYCLE", ("left_of", "b", "a")), found)

    # ---- NESTING-WITHOUT-RELATION

    def test_nesting_shows_kept_composition_or_aggregation(self):
        # a in p (Composition), b in p (Aggregation), p in q (Composition: a is a grandchild of q)
        self.assertEqual(self.gate2("inside(a,p)", "inside(b,p)", "inside(p,q)"), [])

    def test_nesting_in_grouping_needs_no_relation(self):
        self.assertEqual(self.gate2("inside(a,g)", "inside(b,g)"), [])

    def test_nesting_without_any_relation(self):
        self.assertEqual(self.gate2("inside(a,q)"), [("NESTING-WITHOUT-RELATION", ("a", "q"))])

    def test_nesting_with_another_relation_type(self):
        # p -> c is a Serving, not a Composition/Aggregation
        self.assertEqual(self.gate2("inside(c,p)"), [("NESTING-WITHOUT-RELATION", ("c", "p"))])

    def test_nesting_against_the_relation_direction(self):
        # c -> a is a Composition: c may hold a, but a may not hold c
        self.assertEqual(self.gate2("inside(a,c)"), [])
        self.assertEqual(self.gate2("inside(c,a)"), [("NESTING-WITHOUT-RELATION", ("c", "a"))])

    def test_nesting_with_relation_not_kept(self):
        # p -> d is a Composition in the model, but the filter did not keep it
        self.assertEqual(self.gate2("inside(d,p)"), [("NESTING-WITHOUT-RELATION", ("d", "p"))])

    def test_nested_and_beside_reported_once(self):
        self.assertEqual(self.gate2("inside(a,p)", "left_of(a,p)"), [("NESTED-AND-BESIDE", ("left_of", "a", "p"))])


if __name__ == "__main__":
    unittest.main()
