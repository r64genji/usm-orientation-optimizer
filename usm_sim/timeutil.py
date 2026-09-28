"""Integer-millisecond clock helpers. Human times use Asia/Kuala_Lumpur."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def parse_start(event_date: str, start_time_local: str, timezone_name: str) -> datetime:
    tz = ZoneInfo(timezone_name)
    date_part = datetime.fromisoformat(event_date).date()
    time_part = time.fromisoformat(start_time_local)
    return datetime.combine(date_part, time_part, tzinfo=tz)


def to_ms(duration_s: int | float) -> int:
    return int(round(float(duration_s) * 1000.0))


def ms_to_s(time_ms: int) -> float:
    return time_ms / 1000.0


def local_iso(start_dt: datetime, time_ms: int) -> str:
    stamp = start_dt + timedelta(milliseconds=time_ms)
    return stamp.isoformat(timespec="seconds")


def unix_ns_to_local(ns: int, timezone_name: str) -> datetime:
    tz = ZoneInfo(timezone_name)
    sec, nsec = divmod(int(ns), 1_000_000_000)
    return datetime.fromtimestamp(sec, tz=tz).replace(microsecond=nsec // 1000)
