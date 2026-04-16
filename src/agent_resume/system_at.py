from __future__ import annotations

import subprocess


def schedule_once_with_at(command: str, at_time_spec: str) -> None:
    proc = subprocess.run(
        ["at", at_time_spec],
        input=f"{command}\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to schedule with at: {proc.stderr.strip()}")
