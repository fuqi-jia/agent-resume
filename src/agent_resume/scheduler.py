from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from agent_resume.config import load_config
from agent_resume.models import Job
from agent_resume.storage import Storage
from agent_resume.system_at import schedule_once_with_at
from agent_resume.system_cron import add_or_replace_cron_job
from agent_resume.templates import parse_prompt_file, template_prompt
from agent_resume.utils import generate_job_id, now_iso, parse_when_expression, to_at_timespec


def collect_prompts(
    prompt: list[str] | None = None,
    template: list[str] | None = None,
    prompt_file: list[str] | None = None,
    prompt_dir: str | None = None,
) -> list[str]:
    prompts: list[str] = []
    for p in prompt or []:
        prompts.append(p)
    for t in template or []:
        prompts.append(template_prompt(t))
    for pfile in prompt_file or []:
        prompts.extend(parse_prompt_file(Path(pfile).expanduser().resolve()))
    if prompt_dir:
        base = Path(prompt_dir).expanduser().resolve()
        for item in sorted(base.glob("*")):
            if item.is_file():
                prompts.extend(parse_prompt_file(item))
    if not prompts:
        raise ValueError("No prompts provided. Use --prompt, --template, --prompt-file, or --prompt-dir.")
    return prompts


def create_runner_script(storage: Storage, job_id: str) -> Path:
    runner = storage.runners_dir / f"{job_id}.sh"
    runner.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\npython -m agent_resume.runner_exec --job-id "
        + shlex.quote(job_id)
        + "\n",
        encoding="utf-8",
    )
    runner.chmod(0o755)
    return runner


def _make_job(
    cfg: dict[str, Any],
    job_type: str,
    project_dir: str,
    session_id: str,
    prompts: list[str],
    queue_mode: str | None,
    on_prompt_failure: str | None,
    prompt_interval_seconds: int | None,
    concurrency_policy: str | None,
    agent_type: str | None,
    agent_bin: str | None,
) -> tuple[Storage, Job]:
    storage = Storage(cfg["storage_dir"])
    storage.ensure_dirs()
    job_id = generate_job_id()
    defaults = cfg.get("defaults", {})
    job = Job(
        job_id=job_id,
        type=job_type,
        project_dir=str(Path(project_dir).expanduser().resolve()),
        session_id=session_id,
        prompt_queue=prompts,
        current_prompt_index=0,
        queue_status="pending",
        status="scheduled",
        log_file_path=str(storage.log_path(job_id)),
        runner_script_path="",
        created_at=now_iso(),
        queue_mode=queue_mode or defaults.get("queue_mode", "resume"),
        on_prompt_failure=on_prompt_failure or defaults.get("on_prompt_failure", "stop"),
        prompt_interval_seconds=int(prompt_interval_seconds if prompt_interval_seconds is not None else defaults.get("prompt_interval_seconds", 0)),
        concurrency_policy=concurrency_policy or defaults.get("concurrency_policy", "skip"),
        agent_type=agent_type or cfg.get("default_agent_type", "claude"),
        agent_bin=agent_bin or cfg.get("default_agent_bin"),
    )
    return storage, job


def schedule_once(
    project_dir: str,
    session_id: str,
    time_expr: str,
    prompts: list[str],
    config_file: str | None = None,
    queue_mode: str | None = None,
    on_prompt_failure: str | None = None,
    prompt_interval_seconds: int | None = None,
    concurrency_policy: str | None = None,
    agent_type: str | None = None,
    agent_bin: str | None = None,
) -> Job:
    cfg = load_config(config_file)
    storage, job = _make_job(
        cfg,
        "once",
        project_dir,
        session_id,
        prompts,
        queue_mode,
        on_prompt_failure,
        prompt_interval_seconds,
        concurrency_policy,
        agent_type,
        agent_bin,
    )
    runner = create_runner_script(storage, job.job_id)
    job.runner_script_path = str(runner)
    when = parse_when_expression(time_expr)
    job.schedule_time = when.isoformat()
    schedule_once_with_at(f"cd {shlex.quote(job.project_dir)} && {shlex.quote(str(runner))}", to_at_timespec(when))
    storage.upsert_job(job)
    return job


def schedule_recurring(
    project_dir: str,
    session_id: str,
    cron_expr: str,
    prompts: list[str],
    config_file: str | None = None,
    queue_mode: str | None = None,
    on_prompt_failure: str | None = None,
    prompt_interval_seconds: int | None = None,
    concurrency_policy: str | None = None,
    agent_type: str | None = None,
    agent_bin: str | None = None,
) -> Job:
    cfg = load_config(config_file)
    storage, job = _make_job(
        cfg,
        "recurring",
        project_dir,
        session_id,
        prompts,
        queue_mode,
        on_prompt_failure,
        prompt_interval_seconds,
        concurrency_policy,
        agent_type,
        agent_bin,
    )
    runner = create_runner_script(storage, job.job_id)
    job.runner_script_path = str(runner)
    job.cron_expr = cron_expr
    add_or_replace_cron_job(job.job_id, cron_expr, f"cd {shlex.quote(job.project_dir)} && {shlex.quote(str(runner))}")
    storage.upsert_job(job)
    return job


def run_job_now(job_id: str, config_file: str | None = None) -> int:
    cmd = ["python", "-m", "agent_resume.runner_exec", "--job-id", job_id]
    if config_file:
        cmd.extend(["--config", config_file])
    proc = subprocess.run(cmd, text=True, check=False)
    return proc.returncode
