# Lumora Backend

Simple YouTube metadata + download service for **Lumora Downloader**.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/api/info?url=YOUTUBE_URL` | Video title, channel, thumbnail, duration, formats |
| GET | `/api/download?url=...&format=mp4&quality=720` | Streams the file for download |

### Query parameters for `/api/download`

- `url` **(required)** – full YouTube URL
- `format` – `mp4` (default) or `mp3` / `audio`
- `quality` – `360`, `480`, `720` (default), `1080`, or `highest`

---

## Local development

```bash
cd lumora-backend
npm install
npm start
```

Server runs at `http://localhost:3000`

---

## Deploy (recommended free options)

### 1. Railway (easiest)

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Or use Railway CLI:
   ```bash
   npm i -g @railway/cli
   railway login
   railway init
   railway up
   ```
3. Copy the generated public URL (e.g. `https://lumora-backend-production.up.railway.app`)

### 2. Render

1. [render.com](https://render.com) → New → Web Service
2. Connect your repo (or upload the folder)
3. Build command: `npm install`
4. Start command: `npm start`
5. Free tier works fine for light use

### 3. Fly.io

```bash
fly launch
fly deploy
```

---

## After deploying

Copy your public URL (example):

```
https://your-lumora-backend.up.railway.app
```

Then tell me the URL and I will update the **Lumora Downloader** HTML to use it.

---

## Notes

- Uses `@distube/ytdl-core` (maintained fork of ytdl-core)
- Rate limited to 30 requests / minute / IP
- Streams the file directly (no temporary storage)
- Works on mobile browsers when called from the frontend

If downloads start failing in the future (YouTube changes), the most robust long-term solution is to switch the backend to `yt-dlp`. I can help you do that later if needed.
