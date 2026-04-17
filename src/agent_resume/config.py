from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_resume.utils import expand_path

DEFAULT_CONFIG = {
    "default_agent_type": "claude",
    "default_agent_bin": "claude",
    "storage_dir": "~/.agent-resume",
    "log_dir": "~/.agent-resume/logs",
    "runner_dir": "~/.agent-resume/runners",
    "defaults": {
        "queue_mode": "resume",
        "on_prompt_failure": "stop",
        "prompt_interval_seconds": 0,
        "concurrency_policy": "skip",
        "schedule_dir": ".",
        "schedule_delay": "now + 4 hours",
    },
    "claude": {
        "command_template": "{agent_bin} {extra_flags} --resume {session_id} --print {prompt}",
        "extra_flags": "",
        "usage_limit_patterns": [
            "You're out of extra usage",
            "rate limit",
            "quota exceeded",
        ],
    },
}


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required for config YAML support.") from exc
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def config_path(config_file: str | None = None) -> Path:
    if config_file:
        return expand_path(config_file)
    return expand_path("~/.config/agent-resume/config.yaml")


def load_config(config_file: str | None = None) -> dict[str, Any]:
    path = config_path(config_file)
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    return _deep_merge(DEFAULT_CONFIG, _load_yaml(path))


def write_default_config(config_file: str | None = None) -> Path:
    path = config_path(config_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required for config YAML support.") from exc
    path.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False), encoding="utf-8")
    return path
