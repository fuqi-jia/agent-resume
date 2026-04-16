from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Job:
    job_id: str
    type: str
    project_dir: str
    session_id: str
    prompt_queue: list[str] = field(default_factory=list)
    current_prompt_index: int = 0
    queue_status: str = "pending"
    schedule_time: str | None = None
    cron_expr: str | None = None
    status: str = "scheduled"
    log_file_path: str = ""
    runner_script_path: str = ""
    last_exit_code: int | None = None
    last_failure_reason: str | None = None
    created_at: str = ""
    queue_mode: str = "resume"
    on_prompt_failure: str = "stop"
    prompt_interval_seconds: int = 0
    concurrency_policy: str = "skip"
    agent_type: str = "claude"
    agent_bin: str | None = None
    paused: bool = False
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        return cls(**data)
