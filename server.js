/**
 * Lumora Backend
 * --------------
 * Simple YouTube info + download service for the Lumora Downloader frontend.
 *
 * Endpoints:
 *   GET  /                 → health check
 *   GET  /api/info?url=    → video metadata (title, channel, thumbnail, formats)
 *   GET  /api/download     → stream video (mp4) or audio
 *       query params:
 *         url      (required) YouTube URL
 *         format   "mp4" | "mp3" | "audio"   (default: mp4)
 *         quality  "360" | "480" | "720" | "1080" | "highest"  (default: 720)
 *
 * Deploy on Railway / Render / Fly.io / any Node host.
 */

const express = require('express');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const ytdl = require('@distube/ytdl-core');

const app = express();
const PORT = process.env.PORT || 3000;

// ---------- Middleware ----------
app.use(cors({
  origin: '*', // tighten this in production if you want
  methods: ['GET'],
}));

app.use(express.json());

// Basic rate limiting (protect free tiers)
const limiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 30,             // 30 requests per minute per IP
  message: { error: 'Too many requests. Please wait a moment.' },
});
app.use('/api/', limiter);

// ---------- Helpers ----------
function extractVideoId(url) {
  try {
    return ytdl.getVideoID(url);
  } catch {
    return null;
  }
}

function pickFormat(formats, { format = 'mp4', quality = '720' } = {}) {
  const isAudio = format === 'mp3' || format === 'audio';

  if (isAudio) {
    // Prefer highest quality audio-only
    const audioFormats = formats
      .filter(f => f.hasAudio && !f.hasVideo)
      .sort((a, b) => (b.audioBitrate || 0) - (a.audioBitrate || 0));

    return audioFormats[0] || formats.find(f => f.hasAudio);
  }

  // Video
  const height = quality === 'highest' ? 9999 : parseInt(quality, 10) || 720;

  // Prefer progressive (has both audio+video) first
  const progressive = formats
    .filter(f => f.hasVideo && f.hasAudio && f.container === 'mp4')
    .filter(f => (f.height || 0) <= height)
    .sort((a, b) => (b.height || 0) - (a.height || 0));

  if (progressive.length) return progressive[0];

  // Fallback: highest video-only under the height limit
  const videoOnly = formats
    .filter(f => f.hasVideo && f.container === 'mp4')
    .filter(f => (f.height || 0) <= height)
    .sort((a, b) => (b.height || 0) - (a.height || 0));

  return videoOnly[0] || formats.find(f => f.hasVideo);
}

// ---------- Routes ----------

// Health
app.get('/', (req, res) => {
  res.json({
    status: 'ok',
    service: 'Lumora Backend',
    version: '1.0.0',
    endpoints: {
      info: '/api/info?url=YOUTUBE_URL',
      download: '/api/download?url=YOUTUBE_URL&format=mp4&quality=720',
    },
  });
});

// Video info
app.get('/api/info', async (req, res) => {
  const { url } = req.query;

  if (!url) {
    return res.status(400).json({ error: 'Missing "url" query parameter' });
  }

  const videoId = extractVideoId(url);
  if (!videoId) {
    return res.status(400).json({ error: 'Invalid YouTube URL' });
  }

  try {
    const info = await ytdl.getInfo(url);

    const formats = info.formats.map(f => ({
      itag: f.itag,
      quality: f.qualityLabel || f.audioBitrate + 'kbps',
      container: f.container,
      hasVideo: f.hasVideo,
      hasAudio: f.hasAudio,
      contentLength: f.contentLength,
    }));

    res.json({
      videoId,
      title: info.videoDetails.title,
      channel: info.videoDetails.author.name,
      channelUrl: info.videoDetails.author.channel_url,
      thumbnail: info.videoDetails.thumbnails?.slice(-1)[0]?.url
        || `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
      duration: parseInt(info.videoDetails.lengthSeconds, 10),
      description: info.videoDetails.description?.slice(0, 300),
      formats,
    });
  } catch (err) {
    console.error('Info error:', err.message);
    res.status(500).json({
      error: 'Could not fetch video info',
      details: err.message,
    });
  }
});

// Download / stream
app.get('/api/download', async (req, res) => {
  const { url, format = 'mp4', quality = '720' } = req.query;

  if (!url) {
    return res.status(400).json({ error: 'Missing "url" query parameter' });
  }

  const videoId = extractVideoId(url);
  if (!videoId) {
    return res.status(400).json({ error: 'Invalid YouTube URL' });
  }

  try {
    const info = await ytdl.getInfo(url);
    const chosen = pickFormat(info.formats, { format, quality });

    if (!chosen) {
      return res.status(404).json({ error: 'No suitable format found' });
    }

    const isAudio = format === 'mp3' || format === 'audio';
    const ext = isAudio ? 'mp3' : 'mp4';
    const title = (info.videoDetails.title || 'video')
      .replace(/[^\w\s\-_.]/g, '')
      .slice(0, 80)
      .trim() || 'lumora-download';

    const filename = `${title}.${ext}`;

    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.setHeader('Content-Type', isAudio ? 'audio/mpeg' : 'video/mp4');

    if (chosen.contentLength) {
      res.setHeader('Content-Length', chosen.contentLength);
    }

    // Stream the media
    const stream = ytdl.downloadFromInfo(info, {
      format: chosen,
      filter: isAudio ? 'audioonly' : undefined,
    });

    stream.pipe(res);

    stream.on('error', (err) => {
      console.error('Stream error:', err.message);
      if (!res.headersSent) {
        res.status(500).json({ error: 'Download stream failed' });
      }
    });
  } catch (err) {
    console.error('Download error:', err.message);
    res.status(500).json({
      error: 'Could not start download',
      details: err.message,
    });
  }
});

// ---------- Start ----------
app.listen(PORT, () => {
  console.log(`Lumora Backend running on port ${PORT}`);
  console.log(`Health  → http://localhost:${PORT}/`);
  console.log(`Info    → http://localhost:${PORT}/api/info?url=...`);
  console.log(`Download→ http://localhost:${PORT}/api/download?url=...&format=mp4&quality=720`);
});
