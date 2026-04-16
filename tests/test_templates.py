from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_resume.templates import parse_json_prompt_file, parse_text_prompt_file


class TemplateParseTests(unittest.TestCase):
    def test_parse_text_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "prompts.txt"
            path.write_text("=== PROMPT ===\nA\n\n=== PROMPT ===\nB\n", encoding="utf-8")
            self.assertEqual(parse_text_prompt_file(path), ["A", "B"])

    def test_parse_json_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "prompts.json"
            path.write_text(json.dumps(["a", {"name": "b", "prompt": "c"}]), encoding="utf-8")
            self.assertEqual(parse_json_prompt_file(path), ["a", "c"])


if __name__ == "__main__":
    unittest.main()
