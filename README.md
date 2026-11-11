# Stream grabber

Two GitHub Actions workflows for YouTube live streams:

- **Snapshots** saves one frame from each stream every 2 hours, skipping any stream where it's currently dark.
- **Grab a clip** downloads a chosen stretch of the last 12 hours of a stream and hands you an .mp4.

## Files

| Path | What it does |
|---|---|
| `streams.yml` | The streams: URL, camera latitude/longitude, timezone |
| `.github/workflows/snapshots.yml` | Runs `scripts/snapshot.py` every 2 hours and commits the images |
| `.github/workflows/clip.yml` | Runs `scripts/clip.py` on demand and uploads the .mp4 |
| `scripts/common.py` | Config loading and yt-dlp options shared by both |
| `scripts/clip_input.py`, `clip_youtube.py`, `clip_files.py` | Parts of the clip tool: reading the form, finding segments, downloading and joining |

## Setup

1. Edit `streams.yml` if you want to add or change streams.
2. Open the **Actions** tab, pick **Snapshots**, click **Run workflow**, tick "even where it's dark", and run it. This tests whether YouTube lets GitHub in (see below).

After that, snapshots run on their own.

## Snapshots

Images are committed as `screenshots/<stream>/<date>/<stream>_<date>_<time>.jpg` using each camera's local time. "Daylight" means the sun is above the horizon at the camera; set `min_sun_elevation` in `streams.yml` to -6 to include dawn and dusk.

## Grab a clip

Actions → **Grab a clip** → **Run workflow**, then fill in:

| Field | What to type | Examples |
|---|---|---|
| stream | A name from streams.yml, or any YouTube live URL | summit-west-base |
| start | How long ago the clip starts, or a clock time in the camera's timezone | 3h30m, 45m, 14:30, 2:30pm |
| duration | How long the clip is | 10m, 90s, 1h |
| quality | Maximum resolution | 1080 |

When the run finishes, open it and download the clip from **Artifacts** at the bottom of the page. It arrives as a .zip with the .mp4 inside and is kept for 3 days. Clips are cut on segment boundaries, so they may start a few seconds early and run a few seconds long.

### Optional: also copy clips to Google Drive

1. On your own computer, install [rclone](https://rclone.org/downloads/) and run `rclone config`. Create a remote named exactly `gdrive`, type Google Drive, and complete the browser sign-in.
2. Run `rclone config file`, open that file and copy its contents.
3. In the repo: Settings → Secrets and variables → Actions → New repository secret, name `RCLONE_CONF`, paste.

Clips then also land in a Drive folder called `stream-clips`. To use another folder, add a repository variable `DRIVE_FOLDER`.

## If YouTube blocks GitHub

YouTube often answers cloud servers with "Sign in to confirm you're not a bot". If a run fails with that, pick one:

- **Cookies.** Sign in to YouTube with a spare Google account, export cookies.txt (Netscape format) with a browser extension, and save its contents as the secret `YT_COOKIES`. Redo this when they expire.
- **Your own machine.** Set up a [self-hosted runner](https://docs.github.com/en/actions/hosting-your-own-runners) at home (needs Python 3, ffmpeg and Deno; rclone too for the Drive copy), then add a repository variable `RUNNER` with the value `self-hosted`. This is the most dependable fix.
- **A proxy.** Save a proxy URL as the secret `YT_PROXY`.

## Good to know

- Scheduled runs are often 5 to 30 minutes late.
- A stream needs rewind (DVR) for clips to work, and you can only reach back to the last restart.
- Snapshots add roughly 1 to 2 MB per stream per day. Delete old date folders now and then.
- Private repos get limited free Actions minutes and artifact storage. 1080p clips are roughly 30 to 45 MB per minute, so use 720 for long ones.
- Only record streams you own or have permission to record; YouTube's terms restrict downloading otherwise.
