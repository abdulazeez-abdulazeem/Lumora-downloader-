# Lumora Full Stack (yt-dlp)

Reliable YouTube downloader powered by **yt-dlp**.

## Features

- Beautiful glassmorphism frontend (Lumora UI)
- Video metadata (title, channel, thumbnail, duration)
- Download MP4 (360p / 480p / 720p / 1080p / best)
- Download MP3 audio
- Single deployable project

## Local run

```bash
cd lumora-ytdlp
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# yt-dlp also needs ffmpeg for audio conversion
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open → http://localhost:8000

## Deploy

### Railway (recommended)

1. Create new project on [railway.app](https://railway.app)
2. Deploy from this folder (or GitHub)
3. Railway will detect Python and run the start command
4. Add environment variable if needed: `PORT` (Railway sets it automatically)

**Start command** (set in Railway settings if needed):
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Render

- New Web Service
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Important note about FFmpeg

For **MP3 conversion** the server needs `ffmpeg` installed.

On Railway / Render you may need a custom Dockerfile or a buildpack that includes ffmpeg.

If you only need video (MP4) downloads, it works without ffmpeg.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/info?url=YOUTUBE_URL` | Metadata |
| `GET /api/download?url=...&format=mp4&quality=720` | Stream file |
| `GET /api/download?url=...&format=mp3` | Audio only |

## After deployment

Once you have the public URL (example: `https://lumora-xxxx.up.railway.app`), tell me and I will update the frontend so the Download button talks to your backend instead of third-party sites.
