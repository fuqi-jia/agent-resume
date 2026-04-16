from __future__ import annotations

import json
from pathlib import Path


BUILTIN_TEMPLATES = {
    "continue": "Please continue from the last checkpoint and finish the next concrete step.",
    "summary": "Please summarize current progress, blockers, and next actions.",
}


def template_prompt(name: str) -> str:
    if name not in BUILTIN_TEMPLATES:
        raise KeyError(f"Unknown template: {name}")
    return BUILTIN_TEMPLATES[name]


def parse_text_prompt_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    chunks = [c.strip() for c in text.split("=== PROMPT ===")]
    return [c for c in chunks if c]


def parse_json_prompt_file(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("JSON prompt file must be a list")
    result: list[str] = []
    for item in data:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and "prompt" in item:
            result.append(str(item["prompt"]))
        else:
            raise ValueError("Unsupported JSON prompt item; use string or object with 'prompt'")
    return result


def parse_prompt_file(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return parse_json_prompt_file(path)
    return parse_text_prompt_file(path)
