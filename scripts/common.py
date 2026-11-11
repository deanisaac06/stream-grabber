"""Shared helpers for the snapshot and clip scripts."""

import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "streams.yml"


def load_config():
    with open(CONFIG, encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    streams = config.get("streams") or []
    for stream in streams:
        missing = [key for key in ("name", "url", "lat", "lon", "tz") if key not in stream]
        if missing:
            raise SystemExit(f"streams.yml: entry {stream.get('name', stream)} is missing {', '.join(missing)}")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", str(stream["name"])):
            raise SystemExit(f"streams.yml: name '{stream['name']}' may only use letters, numbers, . _ -")
    return config, streams


def ydl_options(**extra):
    """Options passed to yt-dlp. Cookies and proxy are optional and come from the workflow."""
    options = {"quiet": True, "no_warnings": False, "noplaylist": True, "retries": 3}
    cookie_file = os.environ.get("YT_COOKIES_FILE")
    if cookie_file and Path(cookie_file).is_file() and Path(cookie_file).stat().st_size > 0:
        options["cookiefile"] = cookie_file
    if os.environ.get("YT_PROXY"):
        options["proxy"] = os.environ["YT_PROXY"]
    options.update(extra)
    return options


def explain(error):
    """Turn a yt-dlp error into something a person can act on."""
    text = str(error)
    if "not a bot" in text or "IP is likely being blocked" in text:
        return (text + "\n  -> YouTube is refusing this runner's IP address. Add the YT_COOKIES secret, "
                "or use a self-hosted runner (see README, 'If YouTube blocks GitHub').")
    return text


def summary(line):
    """Print a line and add it to the GitHub run summary page."""
    print(line)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n\n")


def set_output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")
