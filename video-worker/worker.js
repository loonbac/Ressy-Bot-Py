// ----------------------------------------------------------------------------
// Worker: a single Discord selfbot account that can stream one YouTube video
// (Go Live screen share) into a voice channel at a time.
//
// Each worker is fully isolated so several can stream different videos at once:
//   - its own Xvfb virtual display   (:99 + index)
//   - its own PulseAudio null sink   (vsink<index>)  -> ffmpeg captures the
//     sink monitor; Firefox is pinned to it via PULSE_SINK
//   - its own Firefox profile dir
//   - its own ffmpeg x11grab + pulse capture
//   - its own discord-video-stream Streamer/Client
//
// The shared PulseAudio daemon + dbus are started once by entrypoint.sh; each
// worker only loads/unloads its own null-sink module.
// ----------------------------------------------------------------------------
import { spawn } from "node:child_process";
import fs from "node:fs";

import { Client } from "discord.js-selfbot-v13";
import { Streamer, playStream } from "@dank074/discord-video-stream";

const log = (id, ...a) => console.log(`[worker ${id}]`, ...a);

function sh(cmd, args) {
  // Run a short command, resolve with {code, stdout, stderr}. Never rejects.
  return new Promise((resolve) => {
    const p = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    let err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", () => resolve({ code: -1, stdout: out, stderr: err }));
    p.on("exit", (code) => resolve({ code, stdout: out, stderr: err }));
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
   * @param {number} opts.index   slot index (allocates display + sink + port)
   * @param {string} opts.token   Discord USER token
   * @param {object} opts.quality {width,height,fps,bitrate,bitrateMax}
   * @param {number} opts.httpPort shared player HTTP server port
   * @param {string} opts.firefoxBin
   */
  constructor(opts) {
    this.index = opts.index;
    this.token = opts.token;
    this.quality = opts.quality;
    this.httpPort = opts.httpPort;
    this.firefoxBin = opts.firefoxBin || "firefox-esr";
    // Notified by the manager when playback ends or errors (drives the queue).
    this._onPlaybackEnd = opts.onPlaybackEnd || null;

    this.display = `:${99 + opts.index}`;
    this.sink = `vsink${opts.index}`;
    this.profileDir = `/tmp/ff-profile-${opts.index}`;

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
    this._startWaiter = null; // resolver while waiting for the page to start
    this._advancing = false; // guards against concurrent queue advances

    this.streamer = null;
    this.xvfbProc = null;
    this.firefoxProc = null;
    this.ffmpegProc = null;
    this.abort = null;
    this._sinkModule = null;
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
    await this._startXvfb();
    await this._ensureSink();
    this._buildNumber = await resolveBuildNumber();
    await this._login();
    this.status = "idle";
    log(this.index, `ready as ${this.tag} (${this.userId}) on ${this.display}`);
    return this.toJSON();
  }

  async _startXvfb() {
    const { width, height } = this.quality;
    const screen = `${width}x${height}x24`;
    log(this.index, `starting Xvfb ${this.display} (${screen})`);
    this.xvfbProc = spawn(
      "Xvfb",
      [this.display, "-screen", "0", screen, "-ac", "-nolisten", "tcp"],
      { stdio: "ignore" }
    );
    this.xvfbProc.on("exit", (code) =>
      log(this.index, `Xvfb exited ${code}`)
    );
    // wait until the display answers
    for (let i = 0; i < 50; i++) {
      const r = await sh("xdpyinfo", ["-display", this.display]);
      if (r.code === 0) return;
      await sleep(100);
    }
    log(this.index, "WARN: Xvfb did not become ready in time");
  }

  async _ensureSink() {
    // Idempotent: load a dedicated null sink for this worker.
    const r = await sh("pactl", [
      "load-module",
      "module-null-sink",
      `sink_name=${this.sink}`,
      `sink_properties=device.description=${this.sink}`,
    ]);
    if (r.code === 0) {
      this._sinkModule = r.stdout.trim();
      log(this.index, `pulse sink ${this.sink} loaded (module ${this._sinkModule})`);
    } else {
      log(this.index, `pulse sink load failed: ${r.stderr.trim()}`);
    }
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
  // Capture pipeline
  // --------------------------------------------------------------------------
  _launchFirefox(videoId) {
    this._killFirefox();
    const { width, height } = this.quality;
    const target = `http://127.0.0.1:${this.httpPort}/?w=${this.index}&v=${encodeURIComponent(
      videoId
    )}`;
    log(this.index, "launching firefox ->", target);
    fs.mkdirSync(this.profileDir, { recursive: true });
    fs.writeFileSync(
      `${this.profileDir}/user.js`,
      [
        'user_pref("media.autoplay.default", 0);',
        'user_pref("media.autoplay.blocking_policy", 0);',
        'user_pref("media.block-autoplay-until-in-foreground", false);',
        'user_pref("browser.shell.checkDefaultBrowser", false);',
        'user_pref("browser.aboutwelcome.enabled", false);',
        'user_pref("datareporting.policy.dataSubmissionEnabled", false);',
        'user_pref("toolkit.telemetry.enabled", false);',
        'user_pref("full-screen-api.warning.timeout", 0);',
        'user_pref("browser.tabs.warnOnClose", false);',
        'user_pref("browser.sessionstore.resume_from_crash", false);',
      ].join("\n")
    );
    this.firefoxProc = spawn(
      this.firefoxBin,
      [
        "--kiosk",
        "--width",
        String(width),
        "--height",
        String(height),
        "--profile",
        this.profileDir,
        target,
      ],
      {
        env: { ...process.env, DISPLAY: this.display, PULSE_SINK: this.sink },
        stdio: "ignore",
      }
    );
    this.firefoxProc.on("exit", (code) =>
      log(this.index, "firefox exited", code)
    );
  }

  _killFirefox() {
    if (this.firefoxProc) {
      try {
        this.firefoxProc.kill("SIGKILL");
      } catch {}
      this.firefoxProc = null;
    }
  }

  _startCapture() {
    this._killFfmpeg();
    const { width, height, fps, bitrate, bitrateMax } = this.quality;
    // Desfase de audio: el pipeline de video (Firefox -> x11grab -> libx264)
    // tiene más latencia que el audio (pulse, casi instantáneo), así que el
    // audio se adelanta. `-itsoffset` retrasa la entrada de audio para
    // sincronizarlos. Positivo = retrasa audio. Tunable en vivo desde el panel.
    const audioOffset = Number(this.quality.audioOffset) || 0;
    const audioInput = [];
    if (audioOffset > 0) audioInput.push("-itsoffset", String(audioOffset));
    audioInput.push("-thread_queue_size", "512", "-f", "pulse", "-i", `${this.sink}.monitor`);
    const args = [
      "-hide_banner",
      "-loglevel",
      "warning",
      "-thread_queue_size",
      "512",
      "-f",
      "x11grab",
      "-draw_mouse",
      "0",
      "-framerate",
      String(fps),
      "-video_size",
      `${width}x${height}`,
      "-i",
      `${this.display}.0`,
      ...audioInput,
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
      "pipe:1",
    ];
    log(this.index, "starting ffmpeg", `${width}x${height}@${fps}`);
    this.ffmpegProc = spawn("ffmpeg", args, {
      env: { ...process.env, DISPLAY: this.display },
      stdio: ["ignore", "pipe", "inherit"],
    });
    this.ffmpegProc.on("exit", (code) => log(this.index, "ffmpeg exited", code));
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

    log(this.index, `joining voice ${guildId}/${channelId}`);
    await this.streamer.joinVoice(guildId, channelId);

    this._launchFirefox(videoId);

    // Esperar a que la página realmente empiece a reproducir (frames reales en
    // pantalla) antes de capturar. Si arrancamos ffmpeg/x11grab sobre un display
    // en blanco, x11grab no junta frames ("not enough frames to estimate rate")
    // y el pipe NUT sale vacío -> el consumidor falla con "No main startcode
    // found" / "Invalid data found". Gatear en la señal PLAYING elimina la carrera.
    const outcome = await this._waitForStart();
    if (outcome.type === "error") {
      throw new Error("la página reportó un error: " + outcome.reason);
    }
    if (outcome.type === "playing") {
      // dejar que el splash se desvanezca y pinten los primeros frames
      await sleep(800);
    }

    const input = this._startCapture();
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

  // Promesa que resuelve cuando la página señala PLAYING (o /error, o timeout).
  _waitForStart(timeoutMs = 25000) {
    return new Promise((resolve) => {
      let done = false;
      const finish = (v) => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        this._startWaiter = null;
        resolve(v);
      };
      const timer = setTimeout(() => {
        log(this.index, "start signal timeout; capturando igual");
        finish({ type: "timeout" });
      }, timeoutMs);
      this._startWaiter = {
        playing: () => finish({ type: "playing" }),
        error: (reason) => finish({ type: "error", reason }),
      };
    });
  }

  // Called by the manager HTTP server when player.html reports playback started.
  onPlaying() {
    log(this.index, "player started");
    if (this._startWaiter) this._startWaiter.playing();
  }

  // Called by the manager HTTP server when player.html reports the video ended.
  onEnded() {
    if (this._startWaiter) return; // aún no estaba reproduciendo
    if (this.status !== "playing") return;
    log(this.index, "video ended");
    if (this._onPlaybackEnd) this._onPlaybackEnd(this, "video ended");
    else this.stop("video ended").catch(() => {});
  }

  onError(reason) {
    log(this.index, "player error", reason);
    if (this._startWaiter) {
      // Falló durante la carga: que play() rechace y el manager pase al siguiente.
      this._startWaiter.error(reason);
      return;
    }
    if (this.status !== "playing") return;
    if (this._onPlaybackEnd) this._onPlaybackEnd(this, "player error " + reason);
    else this.stop("player error " + reason).catch(() => {});
  }

  async _teardownPlayback(reason) {
    log(this.index, "teardown playback:", reason);
    // Si había un play() esperando la señal PLAYING, abortarlo para que no siga
    // adelante (evita dos playStream solapados al reemplazar/saltar).
    if (this._startWaiter) this._startWaiter.error("reemplazado");
    if (this.abort) {
      try {
        this.abort.abort();
      } catch {}
      this.abort = null;
    }
    this._killFirefox();
    this._killFfmpeg();
    try {
      this.streamer.stopStream();
    } catch {}
    this.current = null;
  }

  async stop(reason = "manual") {
    if (this._startWaiter) this._startWaiter.error("detenido");
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
    if (this._sinkModule) {
      await sh("pactl", ["unload-module", this._sinkModule]);
      this._sinkModule = null;
    }
    if (this.xvfbProc) {
      try {
        this.xvfbProc.kill("SIGKILL");
      } catch {}
      this.xvfbProc = null;
    }
    try {
      fs.rmSync(this.profileDir, { recursive: true, force: true });
    } catch {}
  }
}
