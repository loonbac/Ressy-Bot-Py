// ----------------------------------------------------------------------------
// Worker: a single Discord selfbot account that streams one YouTube video
// (Go Live screen share) into a voice channel at a time.
//
// Pipeline (sin navegador): yt-dlp resuelve las URLs directas del stream de
// YouTube y ffmpeg las transcodifica a H264/Opus en un contenedor NUT que se
// envía como Go Live. No hay Firefox/Xvfb/PulseAudio: bypasea restricciones de
// embed (yt-150), anuncios y el overhead de capturar pantalla. La detección de
// fin de video es nativa (ffmpeg termina cuando el stream se acaba).
// ----------------------------------------------------------------------------
import { spawn } from "node:child_process";

import { Client } from "discord.js-selfbot-v13";
import { Streamer, playStream } from "@dank074/discord-video-stream";

const log = (id, ...a) => console.log(`[worker ${id}]`, ...a);

const YTDLP_BIN = process.env.YTDLP_BIN || "yt-dlp";
// Preferimos avc1 (H264) + mp4a (AAC) por compatibilidad de decodificación;
// si no existen, caemos a lo mejor disponible hasta 1080p (tope de Go Live).
const YTDLP_FORMAT =
  process.env.YTDLP_FORMAT ||
  "bestvideo[height<=?1080][vcodec^=avc1]+bestaudio[acodec^=mp4a]/" +
    "bestvideo[height<=?1080]+bestaudio/best[height<=?1080]/best";
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36";

function sh(cmd, args) {
  // Run a short command, resolve with {code, stdout, stderr}. Never rejects.
  return new Promise((resolve) => {
    const p = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    let err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", (e) => resolve({ code: -1, stdout: out, stderr: String(e?.message || e) }));
    p.on("exit", (code) => resolve({ code, stdout: out, stderr: err }));
  });
}

// discord.js-selfbot-v13@3.7.1 está deprecada y hardcodea un client_build_number
// viejo; el gateway de Discord rechaza ese IDENTIFY (close 4013). Scrapeamos el
// build number actual desde los assets de discord.com una sola vez (cacheado).
// Override por env DISCORD_WS_BUILD_NUMBER. Si falla el scrape, null => la lib
// usa su default.
let _cachedBuild = null;
let _buildFetched = false;
async function resolveBuildNumber() {
  if (process.env.DISCORD_WS_BUILD_NUMBER) {
    return parseInt(process.env.DISCORD_WS_BUILD_NUMBER, 10);
  }
  if (_buildFetched) return _cachedBuild;
  _buildFetched = true;
  const ua =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9210 Chrome/134.0.0.0 Electron/35.3.0 Safari/537.36";
  try {
    const html = await fetch("https://discord.com/app", {
      headers: { "user-agent": ua, accept: "text/html" },
    }).then((r) => r.text());
    const files = [...html.matchAll(/assets\/[^"']+?\.js/g)].map((m) => m[0]);
    // Los últimos scripts suelen contener el build number.
    for (const file of files.reverse().slice(0, 10)) {
      const js = await fetch("https://discord.com/" + file, {
        headers: { "user-agent": ua },
      })
        .then((r) => r.text())
        .catch(() => "");
      const m =
        js.match(/build_number["']?\s*[:=]\s*["']?(\d{5,8})/i) ||
        js.match(/buildNumber["']?\s*[:=]\s*["']?(\d{5,8})/i);
      if (m) {
        _cachedBuild = parseInt(m[1], 10);
        console.log("[manager] build number Discord:", _cachedBuild);
        return _cachedBuild;
      }
    }
    console.log("[manager] no se pudo extraer build number; usando default de la lib");
  } catch (e) {
    console.log("[manager] fetch build number falló:", e?.message || e);
  }
  return null;
}

export class Worker {
  /**
   * @param {object} opts
   * @param {number} opts.index   slot index (solo identifica al worker en logs)
   * @param {string} opts.token   Discord USER token
   * @param {object} opts.quality {width,height,fps,bitrate,bitrateMax}
   * @param {function} [opts.onPlaybackEnd]  (worker, reason) cuando el video termina/falla
   */
  constructor(opts) {
    this.index = opts.index;
    this.token = opts.token;
    this.quality = opts.quality;
    // Notified by the manager when playback ends or errors (drives the queue).
    this._onPlaybackEnd = opts.onPlaybackEnd || null;

    // identity (filled after login)
    this.userId = null;
    this.tag = null;
    this.username = null;
    this.avatar = null;

    this.status = "starting"; // starting | idle | loading | playing | error | stopped
    this.current = null; // {guildId, channelId, videoId} while playing/loading

    // Ownership + per-user queue. Managed by the manager, surfaced in toJSON.
    this.ownerId = null;
    this.ownerName = null;
    this.queue = []; // [{guildId, channelId, videoId, requestedBy}]
    this._advancing = false; // guards against concurrent queue advances
    this._stopping = false; // true mientras hacemos teardown (ignora exit de ffmpeg)

    this.streamer = null;
    this.ffmpegProc = null;
    this.abort = null;
  }

  get busy() {
    return this.status === "playing" || this.status === "loading";
  }

  avatarUrl() {
    if (!this.userId) return null;
    if (!this.avatar) {
      // default avatar bucket
      const idx = Number((BigInt(this.userId) >> 22n) % 6n);
      return `https://cdn.discordapp.com/embed/avatars/${idx}.png`;
    }
    const ext = this.avatar.startsWith("a_") ? "gif" : "png";
    return `https://cdn.discordapp.com/avatars/${this.userId}/${this.avatar}.${ext}?size=128`;
  }

  toJSON() {
    return {
      id: this.userId,
      index: this.index,
      user_id: this.userId,
      tag: this.tag,
      username: this.username,
      avatar_url: this.avatarUrl(),
      status: this.status,
      busy: this.busy,
      current: this.current,
      owner_id: this.ownerId,
      owner_name: this.ownerName,
      queue_length: this.queue.length,
      queue: this.queue.map((q) => ({ video_id: q.videoId, channel_id: q.channelId })),
    };
  }

  // --------------------------------------------------------------------------
  // Lifecycle
  // --------------------------------------------------------------------------
  async start() {
    this._buildNumber = await resolveBuildNumber();
    await this._login();
    this.status = "idle";
    log(this.index, `ready as ${this.tag} (${this.userId})`);
    return this.toJSON();
  }

  _login() {
    return new Promise((resolve, reject) => {
      // El IDENTIFY de la lib deprecada se rechaza si el client_build_number es
      // viejo. Pasamos el build actual (scrapeado en start()) y un capabilities
      // moderno. Si Discord cierra igual, capturamos el close code para diagnosis.
      const capabilities = parseInt(process.env.DISCORD_WS_CAPABILITIES || "16381", 10);
      const ws = { capabilities };
      if (this._buildNumber) {
        ws.properties = { client_build_number: this._buildNumber };
      }
      const client = new Client({ ws });
      this.streamer = new Streamer(client);
      let settled = false;
      let lastClose = null;

      const fail = (e) => {
        if (settled) return;
        settled = true;
        this.status = "error";
        try {
          client.destroy();
        } catch {}
        let msg = e?.message || String(e);
        if (lastClose != null) {
          msg += ` (gateway close ${lastClose})`;
          if (lastClose === 4004) msg += " — token inválido o expirado";
          else if (lastClose === 4013 || lastClose === 4014)
            msg += " — handshake rechazado: confirma que sea un token de USUARIO (no de bot) y reintenta";
        }
        reject(new Error(msg));
      };

      const timer = setTimeout(() => fail(new Error("login timeout")), 45000);

      client.on("ready", () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        const u = client.user;
        this.userId = u?.id || null;
        this.tag = u?.tag || u?.username || null;
        this.username = u?.username || null;
        this.avatar = u?.avatar || null;
        resolve();
      });
      client.on("error", (e) => log(this.index, "client error", e?.message || e));
      client.on("shardDisconnect", (ev) => {
        lastClose = ev?.code ?? null;
        log(this.index, "gateway closed", ev?.code, ev?.reason || "");
      });

      client.login(this.token).catch(fail);
    });
  }

  // --------------------------------------------------------------------------
  // Capture pipeline (yt-dlp -> ffmpeg -> NUT)
  // --------------------------------------------------------------------------
  async _resolveStreams(videoId) {
    const url = `https://www.youtube.com/watch?v=${videoId}`;
    const args = ["-q", "--no-warnings", "--no-playlist", "-f", YTDLP_FORMAT, "-g", url];
    if (process.env.YTDLP_COOKIES) args.unshift("--cookies", process.env.YTDLP_COOKIES);
    log(this.index, "resolviendo streams con yt-dlp...");
    const r = await sh(YTDLP_BIN, args);
    if (r.code !== 0) {
      const why = (r.stderr || "").trim().split("\n").pop() || `code ${r.code}`;
      throw new Error("yt-dlp: " + why.slice(0, 300));
    }
    const urls = r.stdout
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!urls.length) throw new Error("yt-dlp no devolvió streams");
    // [video, audio] si son streams separados, o [progresivo] (video+audio).
    return urls;
  }

  _startCapture(urls) {
    this._killFfmpeg();
    const { width, height, fps, bitrate, bitrateMax } = this.quality;
    // -re pacea la lectura a tiempo real (estamos sirviendo un VOD como live).
    // -reconnect tolera cortes de las URLs de googlevideo.
    const inputFlags = [
      "-re",
      "-user_agent",
      UA,
      "-reconnect",
      "1",
      "-reconnect_streamed",
      "1",
      "-reconnect_delay_max",
      "5",
    ];
    const hasAudio = urls.length >= 2;
    const videoUrl = urls[0];
    const audioUrl = hasAudio ? urls[1] : null;

    const args = ["-hide_banner", "-loglevel", "warning"];
    args.push(...inputFlags, "-i", videoUrl);
    if (hasAudio) args.push(...inputFlags, "-i", audioUrl);
    args.push("-map", "0:v:0", "-map", hasAudio ? "1:a:0" : "0:a:0");
    args.push(
      "-vf",
      `scale=-2:${height},fps=${fps}`,
      "-c:v",
      "libx264",
      "-preset",
      "veryfast",
      "-tune",
      "zerolatency",
      "-profile:v",
      "baseline",
      "-pix_fmt",
      "yuv420p",
      "-b:v",
      `${bitrate}k`,
      "-maxrate",
      `${bitrateMax}k`,
      "-bufsize",
      `${bitrate}k`,
      "-bf",
      "0",
      "-g",
      String(fps),
      "-force_key_frames",
      "expr:gte(t,n_forced*1)",
      "-c:a",
      "libopus",
      "-b:a",
      "128k",
      "-ar",
      "48000",
      "-ac",
      "2",
      "-f",
      "nut",
      "pipe:1"
    );
    log(this.index, "starting ffmpeg", `${width}x${height}@${fps}`, hasAudio ? "(v+a)" : "(progresivo)");
    this.ffmpegProc = spawn("ffmpeg", args, { stdio: ["ignore", "pipe", "inherit"] });
    this.ffmpegProc.on("exit", (code) => {
      log(this.index, "ffmpeg exited", code);
      if (this._stopping) return;
      if (this.status !== "playing") return;
      // Fin natural del video (o se cortó el stream): avanzar la cola.
      if (this._onPlaybackEnd) this._onPlaybackEnd(this, "stream ended");
      else this.stop("stream ended").catch(() => {});
    });
    return this.ffmpegProc.stdout;
  }

  _killFfmpeg() {
    if (this.ffmpegProc) {
      try {
        this.ffmpegProc.kill("SIGKILL");
      } catch {}
      this.ffmpegProc = null;
    }
  }

  // --------------------------------------------------------------------------
  // Playback control
  // --------------------------------------------------------------------------
  async play(guildId, channelId, videoId) {
    if (!["idle", "playing", "loading"].includes(this.status)) {
      throw new Error(`worker no disponible (estado: ${this.status})`);
    }
    if (this.status === "playing" || this.status === "loading") {
      await this._teardownPlayback("nuevo play");
    }

    this.status = "loading";
    this.current = { guildId, channelId, videoId };

    // Resolver streams ANTES de unirse al canal: si el video no existe / es
    // privado / geo-bloqueado, fallamos limpio sin entrar a la voz.
    const urls = await this._resolveStreams(videoId);

    log(this.index, `joining voice ${guildId}/${channelId}`);
    await this.streamer.joinVoice(guildId, channelId);

    this._stopping = false;
    const input = this._startCapture(urls);
    this.status = "playing";
    this.abort = new AbortController();
    log(this.index, "going live...");
    playStream(
      input,
      this.streamer,
      { type: "go-live", format: "nut" },
      this.abort.signal
    )
      .then(() => log(this.index, "playStream finished"))
      .catch((e) => log(this.index, "playStream error:", e?.message || e));

    return this.toJSON();
  }

  async _teardownPlayback(reason) {
    log(this.index, "teardown playback:", reason);
    this._stopping = true;
    if (this.abort) {
      try {
        this.abort.abort();
      } catch {}
      this.abort = null;
    }
    this._killFfmpeg();
    try {
      this.streamer.stopStream();
    } catch {}
    this.current = null;
  }

  async stop(reason = "manual") {
    await this._teardownPlayback(reason);
    try {
      this.streamer.leaveVoice();
    } catch {}
    if (this.status === "playing" || this.status === "loading") this.status = "idle";
    return this.toJSON();
  }

  async destroy() {
    await this._teardownPlayback("destroy");
    this.status = "stopped";
    try {
      this.streamer?.client?.destroy();
    } catch {}
  }
}
