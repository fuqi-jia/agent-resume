from __future__ import annotations

import json
from pathlib import Path

from agent_resume.models import Job
from agent_resume.utils import expand_path, now_iso


class Storage:
    def __init__(self, storage_dir: str):
        self.storage_dir = expand_path(storage_dir)
        self.jobs_file = self.storage_dir / "jobs.json"
        self.logs_dir = self.storage_dir / "logs"
        self.runners_dir = self.storage_dir / "runners"

    def ensure_dirs(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.runners_dir.mkdir(parents=True, exist_ok=True)
        if not self.jobs_file.exists():
            self.jobs_file.write_text("{}", encoding="utf-8")

    def load_jobs(self) -> dict[str, Job]:
        self.ensure_dirs()
        raw = self.jobs_file.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else {}
        return {k: Job.from_dict(v) for k, v in data.items()}

    def save_jobs(self, jobs: dict[str, Job]) -> None:
        self.ensure_dirs()
        data = {k: v.to_dict() for k, v in jobs.items()}
        self.jobs_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_job(self, job_id: str) -> Job:
        jobs = self.load_jobs()
        if job_id not in jobs:
            raise KeyError(f"Job not found: {job_id}")
        return jobs[job_id]

    def upsert_job(self, job: Job) -> None:
        jobs = self.load_jobs()
        if not job.created_at:
            job.created_at = now_iso()
        job.updated_at = now_iso()
        jobs[job.job_id] = job
        self.save_jobs(jobs)

    def delete_job(self, job_id: str) -> None:
        jobs = self.load_jobs()
        if job_id in jobs:
            del jobs[job_id]
            self.save_jobs(jobs)

    def log_path(self, job_id: str, prompt_index: int | None = None) -> Path:
        if prompt_index is None:
            return self.logs_dir / f"{job_id}.log"
        return self.logs_dir / f"{job_id}_prompt_{prompt_index}.log"
