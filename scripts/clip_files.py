"""Downloading a run of segments and joining them into an .mp4."""

import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from clip_youtube import fetch, segment_url

THREADS = int(os.environ.get("CLIP_THREADS", "4"))


def download_range(ydl, fmt, base, numbers, folder, label):
    done = 0

    def one(number):
        path = folder / f"{label}_{number}"
        path.write_bytes(fetch(ydl, fmt, segment_url(base, number)))
        return path

    paths = []
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        for path in pool.map(one, numbers):
            paths.append(path)
            done += 1
            if done % 20 == 0 or done == len(numbers):
                print(f"  {label}: {done}/{len(numbers)} segments")
    joined = folder / f"{label}.bin"
    with open(joined, "wb") as out:
        for path in paths:
            with open(path, "rb") as part:
                shutil.copyfileobj(part, out)
            path.unlink()
    return joined


def mux(video_path, audio_path, target):
    command = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_path)]
    if audio_path:
        command += ["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0"]
    command += ["-c", "copy", "-movflags", "+faststart", str(target)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg could not build the clip: {result.stderr.strip()[-600:]}")
