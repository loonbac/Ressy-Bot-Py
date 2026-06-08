# Ressy Video Worker-Manager

Pool of Discord **selfbot** accounts ("workers") that stream YouTube videos as a
**Go Live** screen share into voice channels. Each video is resolved with
**yt-dlp** and transcoded directly with **ffmpeg** (no browser), then pushed via
`@dank074/discord-video-stream`. This bypasses embed restrictions (yt-150), ads,
and the overhead of screen capture.

It is **controlled over HTTP** by the Ressy Python bot (`video_player` plugin) —
this service holds no tokens of its own. The bot registers worker tokens at
runtime (from the dashboard), then issues play/stop/next commands.

> ⚠️ Selfbots violate Discord ToS. Use throwaway accounts only. Each worker
> account must already be a **member of the target guild** to join its voice
> channel.

## Architecture

```
Ressy bot (Python)  ──HTTP(bearer)──►  manager.js  ──►  Worker[0]  yt-dlp ─► ffmpeg ─► Go Live
   /ver /siguiente /parar              (control API)     Worker[1]  yt-dlp ─► ffmpeg ─► Go Live
                                                         Worker[N]  ...
```

- Each `Worker` (worker.js) owns one selfbot `Streamer`. On `/ver` it runs
  `yt-dlp -g` to get the direct stream URL(s), pipes them through `ffmpeg`
  (transcode to H264/Opus, NUT container) and goes live. End-of-video is
  detected natively when ffmpeg exits.
- The manager maps each worker to the Discord user that owns it (`ownerId`),
  keeps a **per-user queue**, and advances it on natural end or `/next`.

## Control API (port `MANAGER_PORT`, `Authorization: Bearer <MANAGER_SECRET>`)

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| GET  | `/health` | — | pool stats incl. queued count (no auth) |
| GET  | `/workers` | — | list workers (with owner + queue) |
| POST | `/workers` | `{token}` | validate token + spawn worker, returns user data |
| DELETE | `/workers/:id` | — | stop + remove worker (id = discord user id) |
| POST | `/workers/:id/stop` | — | stop that worker's playback |
| POST | `/play` | `{guildId, channelId, video, ownerId?, ownerName?, workerId?}` | reuse owner's worker / enqueue / pick idle worker |
| POST | `/next` | `{ownerId?, channelId?}` | skip to the next queued video |
| POST | `/stop` | `{ownerId?, channelId?}` | stop playback + clear queue |
| PUT  | `/quality` | `{width,height,fps,bitrate,bitrateMax}` | live quality tuning |

## Run standalone

```
cp .env.example .env   # set MANAGER_SECRET
docker build -t ressy-video-worker .
docker run --rm -p 8081:8081 --env-file .env ressy-video-worker
```

In the full stack it is wired as the `video-worker` service in the root
`docker-compose.yml` and reached by the bot at `http://video-worker:8081`.
