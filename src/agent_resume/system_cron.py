from __future__ import annotations

import subprocess


def _read_crontab() -> list[str]:
    proc = subprocess.run(["crontab", "-l"], text=True, capture_output=True, check=False)
    if proc.returncode != 0 and "no crontab" in (proc.stderr or "").lower():
        return []
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to read crontab: {proc.stderr.strip()}")
    return [line.rstrip("\n") for line in proc.stdout.splitlines()]


def _write_crontab(lines: list[str]) -> None:
    content = "\n".join(lines).strip()
    if content:
        content += "\n"
    proc = subprocess.run(["crontab", "-"], input=content, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to write crontab: {proc.stderr.strip()}")


def add_or_replace_cron_job(job_id: str, cron_expr: str, command: str) -> None:
    marker = f"# agent-resume:{job_id}"
    lines = [ln for ln in _read_crontab() if marker not in ln]
    lines.append(f"{cron_expr} {command} {marker}")
    _write_crontab(lines)


def remove_cron_job(job_id: str) -> None:
    marker = f"# agent-resume:{job_id}"
    lines = [ln for ln in _read_crontab() if marker not in ln]
    _write_crontab(lines)
