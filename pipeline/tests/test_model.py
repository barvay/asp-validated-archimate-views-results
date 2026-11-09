"""Tests of the unique element names the agents' listings rely on (context.check_model).

  .venv/bin/python -m unittest discover tests

No LLM call.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import context  # noqa: E402


class Model(unittest.TestCase):
    def test_unique_names_pass(self):
        context.check_model({"elements": {"a": ("Node", "A"), "b": ("Node", "B")}})

    def test_duplicate_names_are_reported(self):
        m = {"elements": {"a": ("Node", "Same"), "b": ("Device", "Same"), "c": ("Node", "Other")}}
        with self.assertRaisesRegex(context.ModelError, "1 element name.*'Same': a, b"):
            context.check_model(m)

    def test_example_model(self):
        context.check_model()


if __name__ == "__main__":
    unittest.main()
