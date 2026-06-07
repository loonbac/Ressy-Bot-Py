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

    this.display = `:${99 + opts.index}`;
    this.sink = `vsink${opts.index}`;
    this.profileDir = `/tmp/ff-profile-${opts.index}`;

    // identity (filled after login)
    this.userId = null;
    this.tag = null;
    this.username = null;
    this.avatar = null;

    this.status = "starting"; // starting | idle | playing | error | stopped
    this.current = null; // {guildId, channelId, videoId} while playing

    this.streamer = null;
    this.xvfbProc = null;
    this.firefoxProc = null;
    this.ffmpegProc = null;
    this.abort = null;
    this._sinkModule = null;
  }

  get busy() {
    return this.status === "playing";
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
    };
  }

  // --------------------------------------------------------------------------
  // Lifecycle
  // --------------------------------------------------------------------------
  async start() {
    await this._startXvfb();
    await this._ensureSink();
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
      const client = new Client();
      this.streamer = new Streamer(client);
      let settled = false;

      const fail = (e) => {
        if (settled) return;
        settled = true;
        this.status = "error";
        try {
          client.destroy();
        } catch {}
        reject(e instanceof Error ? e : new Error(String(e)));
      };

      const timer = setTimeout(() => fail(new Error("login timeout")), 30000);

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
      "-thread_queue_size",
      "512",
      "-f",
      "pulse",
      "-i",
      `${this.sink}.monitor`,
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
    if (this.status !== "idle" && this.status !== "playing") {
      throw new Error(`worker no disponible (estado: ${this.status})`);
    }
    if (this.busy) await this._teardownPlayback("nuevo play");

    log(this.index, `joining voice ${guildId}/${channelId}`);
    await this.streamer.joinVoice(guildId, channelId);

    this._launchFirefox(videoId);
    const input = this._startCapture();

    this.status = "playing";
    this.current = { guildId, channelId, videoId };
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

  // Called by the manager HTTP server when player.html reports the video ended.
  onEnded() {
    if (this.status !== "playing") return;
    log(this.index, "video ended");
    this.stop("video ended").catch(() => {});
  }

  onError(reason) {
    if (this.status !== "playing") return;
    log(this.index, "player error", reason);
    this.stop("player error " + reason).catch(() => {});
  }

  async _teardownPlayback(reason) {
    log(this.index, "teardown playback:", reason);
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
    await this._teardownPlayback(reason);
    try {
      this.streamer.leaveVoice();
    } catch {}
    if (this.status === "playing") this.status = "idle";
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
