"""Tests of the element colours: gate 3 (asp/gate3/colors.lp) and the colour tables.

  .venv/bin/python -m unittest discover tests

No LLM call. Uses the band fixture of test_bands.py: one element per band and two Groupings.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from asp_tables import frame_colors, layer_colors
from test_bands import BANDS, ELEMENTS, FIXTURE, GEOMETRY, drawio, pipeline


class Colors(unittest.TestCase):
    def setUp(self):
        self.run = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.run)
        patcher = mock.patch.object(pipeline, "MODEL_FACTS", FIXTURE)
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.run / "1_filter.lp").write_text("".join(f'keep_element("{e}").\n' for e in ELEMENTS))
        (self.run / "2_layout.lp").write_text("".join(f'band("{e}", {BANDS[e]}).\n' for e in ELEMENTS) +
                                              'inside("a2", "g1").\n')

    def gate3(self, styles=None) -> list:
        (self.run / "3_view.drawio").write_text(drawio(GEOMETRY, styles=styles), encoding="utf-8")
        with mock.patch("sys.stdout"):
            code = pipeline.check(3, self.run)
        self.assertIn(code, (0, 1))
        result = json.loads((self.run / "3_check.json").read_text(encoding="utf-8"))
        return sorted((v["rule"], tuple(i["id"] for i in v["ids"])) for v in result["violations"])

    def test_band_colours_pass(self):
        self.assertEqual(self.gate3(), [])

    def test_upper_case_hex_passes(self):
        self.assertEqual(self.gate3({"b1": "fillColor=#FFFFB5;strokeColor=#B3B300;"}), [])

    def test_wrong_fill(self):
        # an application colour on a business element
        self.assertEqual(self.gate3({"b1": "fillColor=#b5ffff;strokeColor=#b3b300;"}),
                         [("LAYER-COLOR", ("b1", "fillColor", "#b5ffff", "#ffffb5"))])

    def test_missing_colours_use_drawio_defaults(self):
        self.assertEqual(self.gate3({"t1": ""}),
                         [("LAYER-COLOR", ("t1", "fillColor", "#ffffff", "#c9e7b7")),
                          ("LAYER-COLOR", ("t1", "strokeColor", "#000000", "#5a8f3c"))])

    def test_other_element_must_be_dashed(self):
        self.assertEqual(self.gate3({"g2": "fillColor=#f5f5f5;strokeColor=#999999;"}),
                         [("LAYER-COLOR", ("g2", "dashed", "0", "1"))])

    def test_band_element_must_not_be_dashed(self):
        self.assertEqual(self.gate3({"m1": "fillColor=#ccccff;strokeColor=#6666cc;dashed=1;"}),
                         [("LAYER-COLOR", ("m1", "dashed", "1", "0"))])


class ColourTables(unittest.TestCase):
    def test_every_band_has_element_colours(self):
        self.assertEqual(set(layer_colors()), {"motivation", "business", "application", "technology", "other"})

    def test_elements_match_but_never_equal_their_frame(self):
        # "match": same table row per band; "never equal": no element colour is a frame colour of its band
        layers = layer_colors()
        for band, (_, stroke, fill) in frame_colors().items():
            with self.subTest(band=band):
                element = {layers[band]["fillColor"], layers[band]["strokeColor"]}
                self.assertFalse(element & {stroke, fill})


if __name__ == "__main__":
    unittest.main()
