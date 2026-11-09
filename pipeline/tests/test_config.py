"""Tests of pipeline.toml loading (scripts/run.py load_config): the optional [effort] table.

  .venv/bin/python -m unittest discover tests

No LLM call.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run  # noqa: E402

BASE = """[limits]
max_repairs = 3
max_judge_rounds = 3

[models]
filter = "haiku"
layout = "haiku"
drawio = "haiku"
judge  = "opus"
"""


class Effort(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def load(self, extra: str = "") -> dict:
        path = self.dir / "pipeline.toml"
        path.write_text(BASE + extra, encoding="utf-8")
        return run.load_config(path)

    def test_no_table_is_default(self):
        self.assertEqual(self.load()["effort"], {})

    def test_per_agent(self):
        cfg = self.load('\n[effort]\ndrawio = "medium"\njudge = "high"\n')
        self.assertEqual(cfg["effort"], {"drawio": "medium", "judge": "high"})

    def test_unknown_agent(self):
        with self.assertRaisesRegex(run.RunError, "unknown agent: render"):
            self.load('\n[effort]\nrender = "low"\n')

    def test_unknown_level(self):
        with self.assertRaisesRegex(run.RunError, "drawio = 'fast'"):
            self.load('\n[effort]\ndrawio = "fast"\n')

    def test_repo_config_loads(self):
        run.load_config(ROOT / "pipeline.toml")


class Models(unittest.TestCase):
    """Model overrides of the command line (--model, --filter, ...) and the setup name of the run folder."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = self.dir / "pipeline.toml"
        self.path.write_text(BASE, encoding="utf-8")

    def test_override_resolves_aliases_and_keeps_judge(self):
        models = run.load_config(self.path, {"filter": "sonnet", "layout": None, "drawio": "my-model"})["models"]
        self.assertEqual(models, {"filter": "claude-sonnet-5-5", "layout": "haiku", "drawio": "my-model",
                                  "judge": "opus"})

    def test_openrouter_override_rejected(self):
        with self.assertRaisesRegex(run.RunError, "only for the judge"):
            run.load_config(self.path, {"drawio": "openrouter:x/y"})

    def test_setup_label(self):
        ids = {a: run.ALIASES[a] for a in run.ALIASES}
        for models, label in [(("sonnet",) * 3, "sonnet"),
                              (("haiku", "sonnet", "sonnet"), "sonnet-filter-haiku"),
                              (("sonnet", "sonnet", "haiku"), "sonnet-drawio-haiku"),
                              (("haiku", "sonnet", "opus"), "filter-haiku-layout-sonnet-drawio-opus"),
                              (("x/y", "x/y", "x/y"), "x_y")]:
            with self.subTest(label):
                given = {a: ids.get(m, m) for a, m in zip(run.STEPS, models)}
                self.assertEqual(run.setup_label(given), label)


if __name__ == "__main__":
    unittest.main()
