"""Tests of the band frames: gate 3 (asp/gate3/bands.lp) and the `other` nesting rules of gate 2.

  .venv/bin/python -m unittest discover tests

No LLM call. Fixture model: tests/fixtures/bands/model_facts.lp, one element per band, an
application Grouping g1 that holds a2, and a free Grouping g2 outside every frame.
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

import pipeline  # noqa: E402
from asp_tables import element_style, frame_colors  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/bands/model_facts.lp"
# element id -> vertex label NAME<br><i>TYPE</i> (escaped for the value attribute)
ELEMENT_LABELS = {e: f"{name}&lt;br&gt;&lt;i&gt;{typ}&lt;/i&gt;" for e, typ, name in
                  re.findall(r'^element\("([^"]+)", "([^"]+)", "([^"]+)"\)', FIXTURE.read_text(encoding="utf-8"), re.M)}
ELEMENTS = ["m1", "b1", "a1", "a2", "t1", "g1", "g2"]
BANDS = {"m1": "motivation", "b1": "business", "a1": "application", "a2": "application",
         "t1": "technology", "g1": "other", "g2": "other"}

FRAME_STYLE = frame_colors()

# id -> (x, y, w, h); frames are 700 wide, 60 px apart, boxes 30 px below the frame top and 20 px in
GEOMETRY = {
    "band-motivation": (0, 0, 700, 120), "m1": (20, 40, 160, 60),
    "band-business": (0, 180, 700, 120), "b1": (20, 220, 160, 60),
    "band-application": (0, 360, 700, 220), "a1": (20, 400, 160, 60),
    "g1": (240, 400, 240, 140), "a2": (260, 440, 160, 60),
    "band-technology": (0, 640, 700, 120), "t1": (20, 680, 160, 60),
    "g2": (760, 400, 160, 60),
}


def drawio(geometry: dict, labels: dict | None = None, styles: dict | None = None) -> str:
    cells = []
    for cid, (x, y, w, h) in geometry.items():
        band = cid.removeprefix("band-")
        if band in FRAME_STYLE:
            label, stroke, fill = FRAME_STYLE[band]
            default_style = f"fillColor={fill};strokeColor={stroke};"
        else:
            label, default_style = ELEMENT_LABELS[cid], element_style(BANDS[cid])
        label = (labels or {}).get(cid, label)
        style = (styles or {}).get(cid, default_style)
        cells.append(f'<mxCell id="{cid}" value="{label}" style="html=1;{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    return ('<mxfile host="pipeline"><diagram id="view" name="View"><mxGraphModel><root>'
            '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")


class Bands(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run)
        patcher = mock.patch.object(pipeline, "MODEL_FACTS", FIXTURE)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_inputs(self, elements=ELEMENTS, inside=(("a2", "g1"),)):
        (self.run / "1_filter.lp").write_text("".join(f'keep_element("{e}").\n' for e in elements))
        (self.run / "2_layout.lp").write_text(
            "".join(f'band("{e}", {BANDS[e]}).\n' for e in elements) +
            "".join(f'inside("{a}", "{b}").\n' for a, b in inside))

    def gate(self, n: int) -> list:
        with mock.patch("sys.stdout"):
            code = pipeline.check(n, self.run)
        self.assertIn(code, (0, 1))
        result = json.loads((self.run / f"{n}_check.json").read_text(encoding="utf-8"))
        return sorted((v["rule"], tuple(i["id"] for i in v["ids"])) for v in result["violations"])

    def gate3(self, geometry=GEOMETRY, elements=ELEMENTS, **kw) -> list:
        self.write_inputs(elements)
        (self.run / "3_view.drawio").write_text(drawio(geometry, **kw), encoding="utf-8")
        return self.gate(3)

    # ---- gate 3

    def test_valid_view_passes(self):
        self.assertEqual(self.gate3(), [])

    def test_missing_frame(self):
        geometry = {k: v for k, v in GEOMETRY.items() if k != "band-technology"}
        self.assertEqual(self.gate3(geometry), [("BAND-FRAME-MISSING", ("band-technology",))])

    def test_frame_of_empty_band(self):
        elements = [e for e in ELEMENTS if e != "t1"]
        geometry = {k: v for k, v in GEOMETRY.items() if k != "t1"}
        self.assertEqual(self.gate3(geometry, elements), [("BAND-FRAME-EXTRA", ("band-technology",))])

    def test_frame_label_and_colours(self):
        found = self.gate3(labels={"band-technology": "Technology layer"},
                           styles={"band-business": "fillColor=#FFFBE8;strokeColor=#000000;"})
        self.assertEqual(found, [("BAND-FRAME-STYLE", ("band-business", "strokeColor", "#e6cf6e")),
                                 ("BAND-FRAME-STYLE", ("band-technology", "label", "Technology"))])

    def test_box_without_padding_or_label_space(self):
        geometry = GEOMETRY | {"a1": (10, 400, 160, 60), "m1": (20, 20, 160, 60)}
        self.assertEqual(self.gate3(geometry), [("BOX-OUTSIDE-FRAME", ("a1", "band-application")),
                                                ("BOX-OUTSIDE-FRAME", ("m1", "band-motivation"))])

    def test_grouping_belongs_to_the_frame_of_its_contents(self):
        # g1 holds an application element, so it must be inside the application frame
        geometry = GEOMETRY | {"g1": (760, 500, 240, 140), "a2": (780, 540, 160, 60)}
        self.assertEqual(self.gate3(geometry), [("BOX-OUTSIDE-FRAME", ("a2", "band-application")),
                                                ("BOX-OUTSIDE-FRAME", ("g1", "band-application"))])

    def test_other_nested_in_frame_member_belongs_to_the_frame(self):
        # the empty Grouping g2 nested in g1 (application frame) is in the application frame too
        geometry = GEOMETRY | {"g1": (240, 400, 440, 140), "g2": (480, 440, 160, 60)}
        self.write_inputs(inside=(("a2", "g1"), ("g2", "g1")))
        (self.run / "3_view.drawio").write_text(drawio(geometry), encoding="utf-8")
        self.assertEqual(self.gate(3), [])
        self.assertEqual(self.gate(2), [])

    def test_foreign_box_in_frame(self):
        # the free Grouping g2 and the technology node t1 inside the application frame
        geometry = GEOMETRY | {"g2": (500, 400, 160, 60), "t1": (500, 480, 160, 60),
                               "band-technology": (0, 640, 700, 120)}
        found = self.gate3(geometry)
        self.assertIn(("FOREIGN-BOX-IN-FRAME", ("g2", "band-application")), found)
        self.assertIn(("FOREIGN-BOX-IN-FRAME", ("t1", "band-application")), found)
        self.assertIn(("BOX-OUTSIDE-FRAME", ("t1", "band-technology")), found)

    def test_frames_out_of_order(self):
        geometry = GEOMETRY | {"band-technology": (0, 560, 700, 200)}
        self.assertEqual(self.gate3(geometry), [("BAND-FRAME-ORDER", ("band-application", "band-technology"))])

    # ---- gate 2

    def test_other_container_of_one_band_passes(self):
        self.write_inputs()
        self.assertEqual(self.gate(2), [])

    def test_other_container_across_bands(self):
        self.write_inputs(inside=(("a2", "g1"), ("t1", "g1")))
        self.assertIn(("OTHER-ACROSS-BANDS", ("g1", "a2", "t1")), self.gate(2))

    def test_other_nested_across_bands(self):
        # b1 (business) inside g2 inside a1 (application): b1 would sit in the application frame
        self.write_inputs(inside=(("a2", "g1"), ("b1", "g2"), ("g2", "a1")))
        self.assertIn(("OTHER-NESTED-ACROSS-BANDS", ("g2", "a1")), self.gate(2))


if __name__ == "__main__":
    unittest.main()
