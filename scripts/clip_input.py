"""Reading what the person typed into the Grab a clip form."""

import os
import re
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

UNITS = {"h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
         "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
         "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1}


class UserError(Exception):
    """A problem the person running the workflow can fix."""


def parse_duration(text):
    """'3h30m' -> 12600, '90s' -> 90, '10' -> 600 (a bare number is minutes)."""
    cleaned = re.sub(r"\bago\b", "", text.strip().lower()).strip()
    if re.fullmatch(r"\d+(\.\d+)?", cleaned):
        return float(cleaned) * 60
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*([a-z]+)", cleaned)
    leftover = re.sub(r"(\d+(?:\.\d+)?)\s*([a-z]+)", "", cleaned).strip(" ,")
    if not parts or leftover or any(unit not in UNITS for _, unit in parts):
        raise UserError(f"Couldn't read '{text}' as a length of time. Examples: 10m, 90s, 1h, 3h30m")
    return sum(float(number) * UNITS[unit] for number, unit in parts)


def parse_start(text, tz, now):
    """Return the clip start as an aware UTC datetime."""
    cleaned = text.strip().lower()
    clock = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", cleaned)
    if clock and (clock.group(2) is not None or clock.group(3)):
        hour, minute, half = int(clock.group(1)), int(clock.group(2) or 0), clock.group(3)
        if half:
            if not 1 <= hour <= 12:
                raise UserError(f"'{text}' isn't a valid clock time")
            hour = hour % 12 + (12 if half == "pm" else 0)
        if hour > 23 or minute > 59:
            raise UserError(f"'{text}' isn't a valid clock time")
        local_now = now.astimezone(tz)
        start = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start > local_now:  # that time hasn't happened yet today, so they mean yesterday
            start -= timedelta(days=1)
        return start.astimezone(timezone.utc)
    return now - timedelta(seconds=parse_duration(cleaned))


def resolve_stream(value, streams):
    """Return (name, url, timezone) for a stream name or a YouTube URL."""
    value = value.strip()
    if re.match(r"https?://", value):
        match = next((s for s in streams if s["url"] == value), None)
        return (match["name"] if match else "clip"), value, ZoneInfo(match["tz"] if match else os.environ.get("CLIP_TZ", "UTC"))
    match = next((s for s in streams if str(s["name"]).lower() == value.lower()), None)
    if not match:
        names = ", ".join(str(s["name"]) for s in streams) or "(none yet)"
        raise UserError(f"No stream called '{value}' in streams.yml. Available: {names}")
    return match["name"], match["url"], ZoneInfo(match["tz"])
