"""Save one frame from every stream in streams.yml where it is currently daylight."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import elevation
from yt_dlp import YoutubeDL

from common import ROOT, explain, load_config, summary, ydl_options

OUT = ROOT / "screenshots"
MAX_HEIGHT = int(os.environ.get("SNAPSHOT_MAX_HEIGHT", "1080"))


def sun_elevation(stream, when):
    return elevation(Observer(latitude=float(stream["lat"]), longitude=float(stream["lon"])), when)


def grab_frame(stream, when):
    selector = f"b[height<={MAX_HEIGHT}]/bv*[height<={MAX_HEIGHT}]/b/bv*"
    with YoutubeDL(ydl_options(format=selector)) as ydl:
        info = ydl.extract_info(stream["url"], download=False)
    if info.get("live_status") != "is_live":
        raise RuntimeError(f"not live right now (status: {info.get('live_status')})")

    candidates = info.get("requested_formats") or [info]
    fmt = next((f for f in candidates if f.get("vcodec") not in (None, "none")), candidates[0])

    local = when.astimezone(ZoneInfo(stream["tz"]))
    folder = OUT / stream["name"] / local.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{stream['name']}_{local.strftime('%Y-%m-%d_%H%M')}.jpg"

    command = ["ffmpeg", "-y", "-loglevel", "error"]
    headers = fmt.get("http_headers") or {}
    if headers:
        command += ["-headers", "".join(f"{key}: {value}\r\n" for key, value in headers.items())]
    command += ["-i", fmt["url"], "-frames:v", "1", "-update", "1", "-q:v", "2", str(target)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg could not read a frame: {result.stderr.strip()[-400:]}")
    return target


def main():
    config, streams = load_config()
    threshold = float(config.get("min_sun_elevation", 0))
    force = os.environ.get("FORCE", "").lower() == "true"
    now = datetime.now(timezone.utc)
    saved, skipped, failed = [], [], []

    for stream in streams:
        height = sun_elevation(stream, now)
        if height < threshold and not force:
            skipped.append(stream["name"])
            print(f"{stream['name']}: dark (sun at {height:.1f} degrees), skipping")
            continue
        try:
            target = grab_frame(stream, now)
            saved.append(stream["name"])
            print(f"{stream['name']}: saved {target.relative_to(ROOT)}")
        except Exception as error:  # one bad stream should not stop the others
            failed.append(stream["name"])
            print(f"{stream['name']}: FAILED - {explain(error)}", file=sys.stderr)

    summary(f"Snapshots: {len(saved)} saved, {len(skipped)} skipped (dark), {len(failed)} failed"
            + (f" ({', '.join(failed)})" if failed else ""))

    # Fail the run only when nothing worked, which usually means YouTube is blocking the runner.
    if failed and not saved:
        sys.exit(1)


if __name__ == "__main__":
    main()
