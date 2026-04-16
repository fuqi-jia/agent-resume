from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def expand_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def generate_job_id(prefix: str = "job") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def parse_when_expression(expr: str) -> datetime:
    text = expr.strip().lower()
    if text == "now":
        return datetime.now(tz=UTC)
    m = re.match(r"^now\s*\+\s*(\d+)\s*(minute|minutes|hour|hours|day|days)$", text)
    if not m:
        raise ValueError(f"Unsupported --time expression: {expr}")
    value = int(m.group(1))
    unit = m.group(2)
    if "minute" in unit:
        delta = timedelta(minutes=value)
    elif "hour" in unit:
        delta = timedelta(hours=value)
    else:
        delta = timedelta(days=value)
    return datetime.now(tz=UTC) + delta


def to_at_timespec(dt: datetime) -> str:
    local_dt = dt.astimezone()
    return local_dt.strftime("%H:%M %Y-%m-%d")
