"""Download a past stretch of a YouTube live stream from its rewind buffer.

Inputs come from environment variables set by the workflow: STREAM, START,
DURATION and QUALITY (see README). A live stream is served as numbered segments
a few seconds long, so we count back from the newest one to the wanted time,
download that range, and join it with ffmpeg.
"""

import math
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from yt_dlp import YoutubeDL

from clip_files import download_range, mux
from clip_input import UserError, parse_duration, parse_start, resolve_stream
from clip_youtube import pick_formats, probe, refine_start, segment_seconds
from common import ROOT, explain, load_config, set_output, summary, ydl_options

OUT = ROOT / "clips"
MAX_LOOKBACK_HOURS = float(os.environ.get("MAX_LOOKBACK_HOURS", "12"))
MAX_CLIP_MINUTES = float(os.environ.get("MAX_CLIP_MINUTES", "120"))


def run():
    _, streams = load_config()
    name, url, tz = resolve_stream(os.environ.get("STREAM", ""), streams)
    try:
        max_height = int(re.sub(r"\D", "", os.environ.get("QUALITY", "1080")) or 1080)
    except ValueError:
        max_height = 1080

    now = datetime.now(timezone.utc)
    start = parse_start(os.environ.get("START", ""), tz, now)
    length = parse_duration(os.environ.get("DURATION", "10m"))
    if length <= 0:
        raise UserError("The clip length has to be more than zero.")
    if length > MAX_CLIP_MINUTES * 60:
        raise UserError(f"Clips are capped at {MAX_CLIP_MINUTES:g} minutes. Ask for a shorter one or split it up.")
    if start >= now:
        raise UserError("The start time has to be in the past.")
    if (now - start).total_seconds() > MAX_LOOKBACK_HOURS * 3600:
        raise UserError(f"That starts more than {MAX_LOOKBACK_HOURS:g} hours ago, which is further back than this tool reaches.")
    end = start + timedelta(seconds=length)
    to_live_edge = end >= now
    if to_live_edge:
        end = now
        print("The clip would run past the present moment, so it ends at 'now'.")

    local_start, local_end = start.astimezone(tz), end.astimezone(tz)
    print(f"Stream: {name}  ({url})")
    print(f"Clip:   {local_start:%Y-%m-%d %H:%M:%S} to {local_end:%H:%M:%S} {local_start:%Z}")

    OUT.mkdir(exist_ok=True)
    target = OUT / f"{name}_{local_start:%Y-%m-%d_%H%M%S}-{local_end:%H%M%S}.mp4"
    work = Path(tempfile.mkdtemp(prefix="clip_"))
    try:
        with YoutubeDL(ydl_options(live_from_start=True)) as ydl:
            info = ydl.extract_info(url, download=False)
            video, audio = pick_formats(info, max_height)
            video_base, head = probe(video)
            audio_base = None
            if audio:
                audio_base, audio_head = probe(audio)
                head = min(head, audio_head)

            # Audio segments are small, so use them for the timing measurements
            ref_fmt, ref_base = (audio, audio_base) if audio else (video, video_base)
            seg_seconds = segment_seconds(ydl, ref_fmt, ref_base, head, float(video.get("target_duration") or 5))
            first = max(head - math.ceil((time.time() - start.timestamp()) / seg_seconds), 0)
            first = refine_start(ydl, ref_fmt, ref_base, first, head, start.timestamp(), seg_seconds)
            count = math.ceil((end - start).total_seconds() / seg_seconds) + 1
            last = head if to_live_edge else min(first + count - 1, head)
            numbers = list(range(first, last + 1))
            if not numbers:
                raise UserError("Nothing to download for that time range.")

            print(f"Video {video.get('height')}p {video.get('vcodec')}, segments {numbers[0]}-{numbers[-1]} "
                  f"({len(numbers)} x {seg_seconds:.2f}s), newest is {head}")
            try:
                video_path = download_range(ydl, video, video_base, numbers, work, "video")
                audio_path = download_range(ydl, audio, audio_base, numbers, work, "audio") if audio else None
            except RuntimeError as error:
                raise UserError(f"{error}\nThat part of the stream may no longer be available. Streams only keep a "
                                "limited rewind buffer, and some have rewind turned off.") from error

        mux(video_path, audio_path, target)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    size_mb = target.stat().st_size / 1e6
    summary(f"Clip ready: {target.name} ({size_mb:.0f} MB), {name}, "
            f"{local_start:%Y-%m-%d %H:%M} to {local_end:%H:%M} {local_start:%Z}. "
            "Download it from the Artifacts section of this run.")
    set_output("file", str(target))
    set_output("name", target.stem)


def main():
    try:
        run()
    except UserError as error:
        summary(f"Couldn't make the clip: {error}")
        sys.exit(1)
    except Exception as error:
        summary(f"Couldn't make the clip: {explain(error)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
