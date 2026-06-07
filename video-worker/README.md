# Ressy Video Worker-Manager

Pool of Discord **selfbot** accounts ("workers") that stream YouTube videos as a
**Go Live** screen share into voice channels. Each video is rendered in a real
**Firefox** (virtual X display) and captured with **ffmpeg**, then pushed via
`@dank074/discord-video-stream`.

It is **controlled over HTTP** by the Ressy Python bot (`video_player` plugin) —
this service holds no tokens of its own. The bot registers worker tokens at
runtime (from the dashboard), then issues play/stop commands.

> ⚠️ Selfbots violate Discord ToS. Use throwaway accounts only. Each worker
> account must already be a **member of the target guild** to join its voice
> channel.

## Architecture

```
Ressy bot (Python)  ──HTTP(bearer)──►  manager.js  ──►  Worker[0]  :99   vsink0  firefox+ffmpeg
   /ver <url>                          (control API)     Worker[1]  :100  vsink1  firefox+ffmpeg
                                                         Worker[N]  ...
```

- `entrypoint.sh` starts dbus + the PulseAudio daemon once.
- Each `Worker` (worker.js) is isolated: own Xvfb display (`:99+idx`), own pulse
  null sink (`vsink<idx>`), own Firefox profile, own ffmpeg, own Streamer.
- `manager.js` exposes the control API and serves `player.html` to Firefox.

## Control API (port `MANAGER_PORT`, `Authorization: Bearer <MANAGER_SECRET>`)

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| GET  | `/health` | — | pool stats (no auth) |
| GET  | `/workers` | — | list workers |
| POST | `/workers` | `{token}` | validate token + spawn worker, returns user data |
| DELETE | `/workers/:id` | — | stop + remove worker (id = discord user id) |
| POST | `/workers/:id/stop` | — | stop that worker's playback |
| POST | `/play` | `{guildId, channelId, video, workerId?}` | pick idle worker + stream |
| POST | `/stop` | `{channelId?}` | stop all (or per-channel) playback |
| PUT  | `/quality` | `{width,height,fps,bitrate,bitrateMax}` | live quality tuning |

## Run standalone

```
cp .env.example .env   # set MANAGER_SECRET
docker build -t ressy-video-worker .
docker run --rm --shm-size=1g -p 8081:8081 --env-file .env ressy-video-worker
```

In the full stack it is wired as the `video-worker` service in the root
`docker-compose.yml` and reached by the bot at `http://video-worker:8081`.
