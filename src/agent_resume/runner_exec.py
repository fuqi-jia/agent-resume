from __future__ import annotations

import argparse
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from agent_resume.config import load_config
from agent_resume.models import Job
from agent_resume.storage import Storage
from agent_resume.utils import now_iso

DEFAULT_USAGE_LIMIT_PATTERNS = ["You're out of extra usage", "rate limit", "quota exceeded"]


def _job_lock_path(storage: Storage, job_id: str) -> Path:
    return storage.runners_dir / f"{job_id}.lock"


def _acquire_lock(storage: Storage, job: Job) -> bool:
    lock = _job_lock_path(storage, job.job_id)
    if lock.exists():
        return False
    lock.write_text(str(time.time()), encoding="utf-8")
    return True


def _release_lock(storage: Storage, job: Job) -> None:
    lock = _job_lock_path(storage, job.job_id)
    if lock.exists():
        lock.unlink()


def _usage_limit_patterns(cfg: dict[str, Any], job: Job) -> list[str]:
    section = cfg.get(job.agent_type, {})
    patterns = section.get("usage_limit_patterns", DEFAULT_USAGE_LIMIT_PATTERNS)
    return [str(p).lower() for p in patterns]


def _command_template(cfg: dict[str, Any], job: Job) -> str:
    section = cfg.get(job.agent_type, {})
    return section.get("command_template", "{agent_bin} --resume {session_id} --print {prompt}")


def _build_command(template: str, cfg: dict[str, Any], job: Job, prompt: str) -> str:
    agent_bin = job.agent_bin or cfg.get("default_agent_bin") or "claude"
    values = {
        "agent_bin": shlex.quote(agent_bin),
        "session_id": shlex.quote(job.session_id),
        "prompt": shlex.quote(prompt),
    }
    return template.format(**values)


def _append_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(content)


def run_job(job_id: str, config_file: str | None = None) -> int:
    cfg = load_config(config_file)
    storage = Storage(cfg["storage_dir"])
    job = storage.get_job(job_id)

    if job.paused or job.status == "paused":
        return 0
    if job.status == "cancelled":
        return 0

    if job.type == "recurring" and job.concurrency_policy == "skip" and not _acquire_lock(storage, job):
        return 0
    if job.type == "recurring" and job.concurrency_policy != "skip" and not _acquire_lock(storage, job):
        job.last_failure_reason = (
            f"Concurrency policy '{job.concurrency_policy}' is not supported. "
            "Only 'skip' is currently implemented."
        )
        job.last_exit_code = 2
        storage.upsert_job(job)
        return 2

    final_code = 0
    template = _command_template(cfg, job)
    usage_patterns = _usage_limit_patterns(cfg, job)
    total = len(job.prompt_queue)

    try:
        if job.queue_mode == "restart":
            job.current_prompt_index = 0
            job.queue_status = "pending"

        _append_log(Path(job.log_file_path), f"\n[{now_iso()}] Run started\n")
        start_idx = job.current_prompt_index
        for idx in range(start_idx, total):
            prompt = job.prompt_queue[idx]
            prompt_log = storage.log_path(job.job_id, idx + 1)
            cmd = _build_command(template, cfg, job, prompt)
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=job.project_dir,
                text=True,
                capture_output=True,
                check=False,
            )
            combined = (proc.stdout or "") + (proc.stderr or "")
            _append_log(prompt_log, combined)
            _append_log(Path(job.log_file_path), f"[{now_iso()}] prompt={idx + 1} exit={proc.returncode}\n")

            lowered = combined.lower()
            if any(p in lowered for p in usage_patterns):
                job.queue_status = "partially_completed"
                job.current_prompt_index = idx
                job.status = "scheduled"
                job.last_failure_reason = "usage_limit_detected"
                job.last_exit_code = proc.returncode
                storage.upsert_job(job)
                final_code = proc.returncode if proc.returncode != 0 else 1
                return final_code

            if proc.returncode != 0:
                job.last_failure_reason = f"prompt_{idx + 1}_failed"
                job.last_exit_code = proc.returncode
                if job.on_prompt_failure == "continue":
                    job.current_prompt_index = idx + 1
                    job.queue_status = "partially_completed"
                    storage.upsert_job(job)
                    if job.prompt_interval_seconds > 0:
                        time.sleep(job.prompt_interval_seconds)
                    continue
                job.current_prompt_index = idx
                job.queue_status = "partially_completed"
                job.status = "failed"
                storage.upsert_job(job)
                final_code = proc.returncode
                return final_code

            job.current_prompt_index = idx + 1
            job.queue_status = "partially_completed" if job.current_prompt_index < total else "completed"
            job.last_exit_code = proc.returncode
            job.last_failure_reason = None
            storage.upsert_job(job)
            if job.prompt_interval_seconds > 0 and idx < total - 1:
                time.sleep(job.prompt_interval_seconds)

        job.status = "completed" if job.type == "once" else "scheduled"
        job.queue_status = "completed"
        job.current_prompt_index = total
        storage.upsert_job(job)
        final_code = 0
        return final_code
    finally:
        if job.type == "recurring":
            _release_lock(storage, job)
        _append_log(Path(job.log_file_path), f"[{now_iso()}] Run finished code={final_code}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    raise SystemExit(run_job(args.job_id, args.config))


if __name__ == "__main__":
    main()
