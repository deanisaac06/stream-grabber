# Stream grabber

Three GitHub Actions workflows for YouTube live ski cams at The Summit at Snoqualmie and Alpental:

- **Snapshots** saves one photo per camera every hour, from 1 hour before sunrise to 1 hour after sunset.
- **Grab a clip** downloads a chosen stretch of the last 12 hours of a stream as an .mp4.
- **Download photos** zips up one camera's photos (or all of them) for download.

## Cameras

| Name | Stream |
|---|---|
| summit-west-base | https://www.youtube.com/watch?v=vhO8nNqg9iw |
| silver-fir-base | https://www.youtube.com/watch?v=H7HwsNLqVC8 |
| summit-central-top | https://www.youtube.com/watch?v=w4Sno8NIjmU |
| alpental-mid | https://www.youtube.com/watch?v=c_XLrUYV8tk |
| alpental-base | https://www.youtube.com/watch?v=8wk81COX2cg |

To add a camera, add an entry to `streams.yml` (name, url, lat, lon, tz) and add the same name to the `options` list in `.github/workflows/download-photos.yml`.

## Files

| Path | What it does |
|---|---|
| `streams.yml` | The cameras (URL, latitude/longitude, timezone) and the photo window |
| `.github/workflows/snapshots.yml` | Runs `scripts/snapshot.py` every hour and commits the photos |
| `.github/workflows/clip.yml` | Runs `scripts/clip.py` on demand and uploads the .mp4 |
| `.github/workflows/download-photos.yml` | Zips a camera's photos for download |
| `scripts/common.py` | Config loading and yt-dlp options shared by the scripts |
| `scripts/clip_input.py`, `clip_youtube.py`, `clip_files.py` | Parts of the clip tool: reading the form, finding segments, downloading and joining |

## Snapshots

Photos are saved as `screenshots/<camera>/<camera>_<date>_<time>.jpg`: one flat folder per camera, named in the camera's local time. Sorting by name puts them in time order, ready to drop into a timelapse.

The photo window is set by `minutes_before_sunrise` and `minutes_after_sunset` in `streams.yml` (both 60). Sunrise and sunset are worked out for each camera's location every day, so the window follows the seasons. Brightness and fog are ignored; it goes by the clock.

To take a photo right now: Actions → **Snapshots** → **Run workflow**, tick "even where it's dark", and run it. Those photos join the timeline too.

## Download photos

Actions → **Download photos** → **Run workflow**, pick a camera (or `all`), and run it. Open the finished run and download the zip under **Artifacts**. Zips are kept for 3 days; run it again anytime. You can also browse `screenshots/` on the Code tab.

## Grab a clip

Actions → **Grab a clip** → **Run workflow**, then fill in:

| Field | What to type | Examples |
|---|---|---|
| stream | A camera name from the table above, or any YouTube live URL | alpental-base |
| start | How long ago the clip starts, or a clock time in the camera's timezone | 3h30m, 45m, 14:30, 2:30pm |
| duration | How long the clip is | 10m, 90s, 1h |
| quality | Maximum resolution | 1080, 720, 480, 360 |

When the run finishes, open it and download the clip from **Artifacts** at the bottom of the page. It arrives as a .zip with the .mp4 inside and is kept for 3 days. Clips are cut on segment boundaries, so they may start a few seconds early and run a few seconds long. Clips only reach back as far as the stream's rewind (up to about 12 hours, and never past a stream restart).

### Optional: also copy clips to Google Drive

1. On your own computer, install [rclone](https://rclone.org/downloads/) and run `rclone config`. Create a remote named exactly `gdrive`, type Google Drive, and complete the browser sign-in.
2. Run `rclone config file`, open that file and copy its contents.
3. In the repo: Settings → Secrets and variables → Actions → New repository secret, name `RCLONE_CONF`, paste.

Clips then also land in a Drive folder called `stream-clips`. To use another folder, add a repository variable `DRIVE_FOLDER`.

## If YouTube blocks GitHub

YouTube often answers cloud servers with "Sign in to confirm you're not a bot". This repo uses the cookies fix. Cookies expire every few weeks: when runs start failing with that error again (GitHub emails you about failed scheduled runs), export fresh cookies and update the `YT_COOKIES` secret.

- **Cookies (in use).** Open an Incognito window, sign in to YouTube with a spare Google account (not your main one), export cookies.txt in Netscape format with the "Get cookies.txt LOCALLY" extension, then close the window without signing out. In the repo: Settings → Secrets and variables → Actions → `YT_COOKIES` → update, and paste the whole file.
- **Your own machine.** Set up a [self-hosted runner](https://docs.github.com/en/actions/hosting-your-own-runners) at home (needs Python 3, ffmpeg and Deno; rclone too for the Drive copy), then add a repository variable `RUNNER` with the value `self-hosted`. This is the most dependable fix.
- **A proxy.** Save a proxy URL as the secret `YT_PROXY`.

## Good to know

- Scheduled runs are often 5 to 30 minutes late, and GitHub occasionally skips one, so expect roughly (not exactly) one photo per hour.
- Daytime photos are roughly 200 to 400 KB each, so with 5 cameras the repo grows by a few GB a year. GitHub starts warning at around 1 to 5 GB, so within a few months either lower the snapshot resolution or move older photos out (for example to Google Drive).
- The repo is public: code, photos, run logs and clip downloads can be seen by anyone, but secrets stay hidden. Only people with write access can start runs. Public repos have no Actions minutes limit.
- 1080p clips are roughly 30 to 45 MB per minute; use 720 for long ones.
- The photos from 2026-11-11 ending in `_1752` and `_1826` are nighttime test shots; leave them out of timelapses if you like.
- Only record streams you own or have permission to record; YouTube's terms restrict downloading otherwise.
