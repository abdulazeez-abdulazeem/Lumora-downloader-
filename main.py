"""
Lumora Backend (yt-dlp)
-----------------------
Reliable YouTube metadata + download service using yt-dlp.

Endpoints:
  GET  /                     → Frontend
  GET  /api/health           → Health check
  GET  /api/info?url=        → Video metadata
  GET  /api/download         → Stream video or audio
       ?url=...&format=mp4|mp3&quality=360|480|720|1080|best
"""

import os
import re
import shutil
import tempfile
import asyncio
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="Lumora Backend", version="2.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Serve the frontend
STATIC_DIR = Path(__file__).parent / "public"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def cleanup_tmpdir(path: str):
    """Remove temporary download directory after response is sent."""
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def get_info(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Lumora yt-dlp", "version": "2.0.0"}


@app.get("/api/info")
async def video_info(url: str = Query(..., description="YouTube URL")):
    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    try:
        info = await asyncio.to_thread(get_info, url)

        # Best thumbnail
        thumb = None
        if info.get("thumbnails"):
            thumb = info["thumbnails"][-1].get("url")
        if not thumb:
            thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        return {
            "videoId": video_id,
            "title": info.get("title"),
            "channel": info.get("uploader") or info.get("channel"),
            "channelUrl": info.get("uploader_url") or info.get("channel_url"),
            "thumbnail": thumb,
            "duration": info.get("duration"),
            "description": (info.get("description") or "")[:300],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not fetch video info: {str(e)}")


@app.get("/api/download")
async def download(
    background_tasks: BackgroundTasks,
    url: str = Query(...),
    format: str = Query("mp4", pattern="^(mp4|mp3|audio)$"),
    quality: str = Query("720", pattern="^(360|480|720|1080|best)$"),
):
    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    is_audio = format in ("mp3", "audio")

    # Build format selector for yt-dlp
    if is_audio:
        format_selector = "bestaudio/best"
        outtmpl = "%(title)s.%(ext)s"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        # Prefer progressive mp4 first (no ffmpeg needed), then fall back to merge
        height = "9999" if quality == "best" else quality
        format_selector = (
            f"best[height<={height}][ext=mp4][vcodec!=none][acodec!=none]/"  # progressive first
            f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"       # merge if needed
            f"best[height<={height}]/"
            f"best"
        )
        postprocessors = []

    # Temporary directory for the download
    tmpdir = tempfile.mkdtemp(prefix="lumora_")

    ydl_opts = {
        "format": format_selector,
        "outtmpl": os.path.join(tmpdir, "%(title).80s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "postprocessors": postprocessors,
        "noplaylist": True,
        "retries": 3,
        "restrictfilenames": True,  # safer filenames
    }

    try:
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if is_audio:
                    # After FFmpegExtractAudio the extension becomes .mp3
                    base, _ = os.path.splitext(filename)
                    candidate = base + ".mp3"
                    if os.path.exists(candidate):
                        filename = candidate
                return filename, info.get("title", "video")

        filepath, title = await asyncio.to_thread(_download)

        if not os.path.exists(filepath):
            # Fallback: look for any media file in the temp dir
            files = list(Path(tmpdir).glob("*"))
            files = [f for f in files if f.suffix.lower() in (".mp4", ".mp3", ".m4a", ".webm", ".mkv")]
            if not files:
                raise FileNotFoundError("Downloaded file not found")
            filepath = str(files[0])

        # Sanitize filename for Content-Disposition
        safe_title = re.sub(r"[^\w\s\-_.]", "", title)[:80].strip() or "lumora"
        ext = "mp3" if is_audio else "mp4"
        download_name = f"{safe_title}.{ext}"

        media_type = "audio/mpeg" if is_audio else "video/mp4"

        # Clean up temp files AFTER the response has been sent
        background_tasks.add_task(cleanup_tmpdir, tmpdir)

        return FileResponse(
            path=filepath,
            media_type=media_type,
            filename=download_name,
        )

    except Exception as e:
        # Clean immediately on error
        cleanup_tmpdir(tmpdir)
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


# Serve frontend at root
@app.get("/")
async def serve_frontend():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"message": "Lumora backend is running. Place index.html in /public"})


# Catch-all for SPA-style routing
@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")
