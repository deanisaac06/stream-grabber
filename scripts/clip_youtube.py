"""Talking to YouTube: choosing formats and finding segments in the rewind buffer."""

import math
import re
import time

from yt_dlp.networking import Request
from yt_dlp.utils import update_url_query

from clip_input import UserError


def pick_formats(info, max_height):
    """Choose the video and audio formats that can be read from the rewind buffer."""
    rewindable = [f for f in info.get("formats") or [] if callable(f.get("fragments"))]
    videos = [f for f in rewindable if f.get("vcodec") not in (None, "none")]
    audios = [f for f in rewindable if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")]
    if not videos:
        if info.get("live_status") != "is_live":
            raise UserError(f"This stream isn't live right now (status: {info.get('live_status')}).")
        raise UserError("YouTube didn't offer any rewindable formats for this stream.")
    fitting = [f for f in videos if (f.get("height") or 0) <= max_height] or [min(videos, key=lambda f: f.get("height") or 0)]
    # Prefer H.264 and AAC at a given size because they play everywhere as .mp4
    video = max(fitting, key=lambda f: (f.get("height") or 0, str(f.get("vcodec")).startswith("avc"), f.get("fps") or 0, f.get("tbr") or 0))
    audio = max(audios, key=lambda f: (str(f.get("acodec")).startswith("mp4a"), f.get("abr") or f.get("tbr") or 0)) if audios else None
    return video, audio


def probe(fmt):
    """Return (segment URL template, number of the newest segment) for a format."""
    first = next(iter(fmt["fragments"]({})), None)
    if not first or not first.get("url") or not first.get("fragment_count"):
        raise UserError("Couldn't read the stream's current position from YouTube. Try again in a minute.")
    return first["url"], int(first["fragment_count"]) - 1


def segment_url(base, number):
    # YouTube puts the segment number in the path (.../sq/123) or in the query (?sq=123)
    if re.search(r"/sq/\d+", base):
        return re.sub(r"/sq/\d+", f"/sq/{number}", base, count=1)
    return update_url_query(base, {"sq": str(number)})


def fetch(ydl, fmt, url, attempts=5):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = ydl.urlopen(Request(url, headers=fmt.get("http_headers") or {}))
            try:
                data = response.read()
            finally:
                response.close()
            if data:
                return data
            last_error = RuntimeError("empty response")
        except Exception as error:  # network hiccups are normal; retry
            last_error = error
            if getattr(error, "status", None) in (403, 404) and attempt >= 2:
                break
        time.sleep(min(2 ** attempt, 15))
    raise RuntimeError(f"segment download failed: {last_error}")


def stamp_of(ydl, fmt, base, number):
    """The capture time (epoch seconds) stamped inside a segment, or None."""
    try:
        data = fetch(ydl, fmt, segment_url(base, number), attempts=2)
    except RuntimeError:
        return None
    match = re.search(rb"Ingestion-Walltime-Us:\s*(\d+)", data[:65536])
    return int(match.group(1)) / 1e6 if match else None


def segment_seconds(ydl, fmt, base, head, fallback):
    """Measure how long one segment lasts from the timestamps of two segments.

    Normal streams use 5 s segments, low-latency ones 2 s or 1 s.
    """
    gap = min(60, head)
    if gap >= 10:
        newer, older = stamp_of(ydl, fmt, base, head), stamp_of(ydl, fmt, base, head - gap)
        if newer and older and newer > older:
            measured = (newer - older) / gap
            if 0.5 <= measured <= 15:
                return measured
    return fallback


def refine_start(ydl, fmt, base, number, head, start_epoch, seg_seconds):
    """Nudge the starting segment using the capture time stamped inside each segment.

    Counting back from the newest segment is close but can drift if the stream
    hiccupped. If the timestamp isn't there, keep the arithmetic answer.
    """
    for _ in range(3):
        stamp = stamp_of(ydl, fmt, base, number)
        if stamp is None:
            return number
        shift = math.floor((start_epoch - stamp) / seg_seconds)
        if shift == 0 or abs(shift) * seg_seconds > 3600:
            return number
        number = min(max(number + shift, 0), head)
    return number
