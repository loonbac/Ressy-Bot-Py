// ----------------------------------------------------------------------------
// Worker-manager daemon.
//
// Manages a pool of Discord selfbot "workers" (one user account each) that
// stream YouTube videos into voice channels. The Ressy Python bot controls it
// over an HTTP control API (bearer-authenticated). A second HTTP server serves
// player.html to the per-worker Firefox instances and receives playback events.
//
// Env (see .env.example):
//   MANAGER_PORT     control API port (default 8081, bound 0.0.0.0)
//   HTTP_PORT        player page port (default 8080, bound 127.0.0.1)
//   MANAGER_SECRET   bearer token the bot must send (optional but recommended)
//   MAX_WORKERS      hard cap on concurrent workers / displays (default 5)
//   WIDTH HEIGHT FPS BITRATE_KBPS BITRATE_MAX_KBPS  default quality
//   FIREFOX_BIN
// ----------------------------------------------------------------------------
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Worker } from "./worker.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const MANAGER_PORT = parseInt(process.env.MANAGER_PORT || "8081", 10);
const HTTP_PORT = parseInt(process.env.HTTP_PORT || "8080", 10);
const MANAGER_SECRET = process.env.MANAGER_SECRET || "";
const FIREFOX_BIN = process.env.FIREFOX_BIN || "firefox-esr";

// Cap de workers concurrentes. Si MAX_WORKERS no se define, se calcula a partir
// de la RAM disponible: cada worker (Firefox + Xvfb + ffmpeg) consume
// ~VIDEO_RAM_PER_WORKER_MB; se reserva VIDEO_RAM_RESERVE_MB para el SO + el
// resto del stack. Tope duro de 24 (índices de display :99..:123).
const PER_WORKER_MB = parseInt(process.env.VIDEO_RAM_PER_WORKER_MB || "1500", 10);
const RESERVE_MB = parseInt(process.env.VIDEO_RAM_RESERVE_MB || "3000", 10);
const HARD_CAP = parseInt(process.env.VIDEO_MAX_WORKERS_CAP || "24", 10);

function autoMaxWorkers() {
  const totalMb = Math.floor(os.totalmem() / (1024 * 1024));
  const budget = Math.max(0, totalMb - RESERVE_MB);
  const n = Math.floor(budget / Math.max(256, PER_WORKER_MB));
  return Math.max(1, Math.min(HARD_CAP, n));
}

const MAX_WORKERS =
  process.env.MAX_WORKERS && process.env.MAX_WORKERS.trim()
    ? Math.max(1, Math.min(HARD_CAP, parseInt(process.env.MAX_WORKERS, 10)))
    : autoMaxWorkers();

const DEFAULT_QUALITY = {
  width: parseInt(process.env.WIDTH || "1280", 10),
  height: parseInt(process.env.HEIGHT || "720", 10),
  fps: parseInt(process.env.FPS || "30", 10),
  bitrate: parseInt(process.env.BITRATE_KBPS || "3000", 10),
  bitrateMax: parseInt(process.env.BITRATE_MAX_KBPS || "4500", 10),
  audioOffset: parseFloat(process.env.VIDEO_AUDIO_OFFSET || "0.3"),
};

const log = (...a) => console.log("[manager]", ...a);

// ----------------------------------------------------------------------------
// YouTube URL -> video id
// ----------------------------------------------------------------------------
function parseVideoId(input) {
  if (!input) return null;
  const s = String(input).trim();
  if (/^[a-zA-Z0-9_-]{11}$/.test(s)) return s;
  let u;
  try {
    u = new URL(s);
  } catch {
    return null;
  }
  const host = u.hostname.replace(/^www\./, "");
  if (host === "youtu.be") {
    const id = u.pathname.slice(1).split("/")[0];
    return /^[a-zA-Z0-9_-]{11}$/.test(id) ? id : null;
  }
  if (host.endsWith("youtube.com")) {
    if (u.searchParams.get("v")) return u.searchParams.get("v");
    const parts = u.pathname.split("/").filter(Boolean);
    if (["embed", "shorts", "live", "v"].includes(parts[0]) && parts[1]) {
      return /^[a-zA-Z0-9_-]{11}$/.test(parts[1]) ? parts[1] : null;
    }
  }
  return null;
}

// ----------------------------------------------------------------------------
// Worker pool
// ----------------------------------------------------------------------------
const workers = new Map(); // userId -> Worker
const usedIndexes = new Set();
let quality = { ...DEFAULT_QUALITY };

function allocIndex() {
  for (let i = 0; i < MAX_WORKERS; i++) {
    if (!usedIndexes.has(i)) {
      usedIndexes.add(i);
      return i;
    }
  }
  return -1;
}

async function addWorker(token) {
  if (!token || typeof token !== "string") {
    const e = new Error("token requerido");
    e.status = 400;
    throw e;
  }
  if (workers.size >= MAX_WORKERS) {
    const e = new Error(`límite de ${MAX_WORKERS} workers alcanzado`);
    e.status = 409;
    throw e;
  }
  const index = allocIndex();
  if (index < 0) {
    const e = new Error("sin slots libres");
    e.status = 409;
    throw e;
  }
  const w = new Worker({
    index,
    token,
    quality,
    httpPort: HTTP_PORT,
    firefoxBin: FIREFOX_BIN,
    onPlaybackEnd: (worker, reason) => autoAdvance(worker, reason),
  });
  try {
    await w.start();
  } catch (err) {
    usedIndexes.delete(index);
    await w.destroy().catch(() => {});
    const e = new Error("token inválido o login falló: " + (err?.message || err));
    e.status = 400;
    throw e;
  }
  // Dedupe by account: if this user is already a worker, keep the old one.
  if (workers.has(w.userId)) {
    usedIndexes.delete(index);
    await w.destroy().catch(() => {});
    return workers.get(w.userId).toJSON();
  }
  workers.set(w.userId, w);
  return w.toJSON();
}

async function removeWorker(id) {
  const w = workers.get(id);
  if (!w) {
    const e = new Error("worker no encontrado");
    e.status = 404;
    throw e;
  }
  workers.delete(id);
  usedIndexes.delete(w.index);
  await w.destroy().catch(() => {});
  return { removed: id };
}

function pickWorker(workerId) {
  if (workerId) {
    const w = workers.get(workerId);
    if (!w) {
      const e = new Error("worker no encontrado");
      e.status = 404;
      throw e;
    }
    return w;
  }
  // Solo workers libres y sin dueño (no robar el worker de otro usuario).
  for (const w of workers.values()) {
    if (w.status === "idle" && !w.ownerId) return w;
  }
  const e = new Error("no hay workers disponibles (todos ocupados)");
  e.status = 409;
  throw e;
}

function workerByOwner(ownerId) {
  if (!ownerId) return null;
  const id = String(ownerId);
  for (const w of workers.values()) if (w.ownerId === id) return w;
  return null;
}

function findOwnerWorker(ownerId, channelId) {
  const mine = workerByOwner(ownerId);
  if (mine) return mine;
  if (channelId) {
    const cid = String(channelId);
    for (const w of workers.values()) {
      if (w.busy && w.current?.channelId === cid) return w;
    }
  }
  return null;
}

// Pasa al siguiente video de la cola del worker, saltando los que fallan.
// Devuelve el toJSON del que quedó reproduciendo, o null si la cola se vació
// (en ese caso detiene el worker y libera la propiedad).
async function autoAdvance(worker, reason) {
  if (!worker) return null;
  if (worker._advancing) return null;
  worker._advancing = true;
  try {
    while (worker.queue.length) {
      const item = worker.queue.shift();
      try {
        const res = await worker.play(item.guildId, item.channelId, item.videoId);
        return { ...res, video_id: item.videoId };
      } catch (err) {
        log("advance item falló:", err?.message || err);
      }
    }
    await worker.stop(reason).catch(() => {});
    worker.ownerId = null;
    worker.ownerName = null;
    return null;
  } finally {
    worker._advancing = false;
  }
}

async function doPlay(w, guildId, channelId, videoId, ownerId, ownerName) {
  if (ownerId) {
    w.ownerId = String(ownerId);
    if (ownerName) w.ownerName = ownerName;
  }
  try {
    const res = await w.play(guildId, channelId, videoId);
    return { ...res, video_id: videoId, queued: false };
  } catch (err) {
    // Video inválido (p.ej. embedding deshabilitado / yt-150). Si el usuario
    // tiene cola, saltamos al siguiente; si no, soltamos el worker.
    if (w.queue.length) {
      const adv = await autoAdvance(w, "play falló");
      if (adv) return { ...adv, skipped: videoId, queued: false };
    }
    await w.stop("play falló").catch(() => {});
    w.ownerId = null;
    w.ownerName = null;
    w.queue = [];
    const e = new Error("no se pudo reproducir: " + (err?.message || err));
    e.status = 502;
    throw e;
  }
}

async function play({ guildId, channelId, video, workerId, ownerId, ownerName }) {
  if (workers.size === 0) {
    const e = new Error("no hay workers configurados");
    e.status = 409;
    throw e;
  }
  const videoId = parseVideoId(video);
  if (!videoId) {
    const e = new Error("URL de YouTube inválida");
    e.status = 400;
    throw e;
  }
  if (!guildId || !channelId) {
    const e = new Error("guildId y channelId requeridos");
    e.status = 400;
    throw e;
  }
  ownerId = ownerId != null ? String(ownerId) : null;

  // Selección explícita de worker (reproducción de prueba desde el dashboard).
  if (workerId) {
    const w = pickWorker(workerId);
    return doPlay(w, guildId, channelId, videoId, ownerId, ownerName);
  }

  // Reusar el worker que este usuario ya tiene asignado. Si está ocupado, va a
  // su cola; si está libre (entre videos), reproduce de una.
  if (ownerId) {
    const mine = workerByOwner(ownerId);
    if (mine) {
      if (mine.busy) {
        mine.queue.push({ guildId, channelId, videoId, requestedBy: ownerId });
        if (ownerName) mine.ownerName = ownerName;
        return {
          queued: true,
          position: mine.queue.length,
          video_id: videoId,
          tag: mine.tag,
          username: mine.username,
          avatar_url: mine.avatarUrl(),
        };
      }
      return doPlay(mine, guildId, channelId, videoId, ownerId, ownerName);
    }
  }

  // Tomar un worker libre.
  const w = pickWorker(null);
  return doPlay(w, guildId, channelId, videoId, ownerId, ownerName);
}

async function nextFor({ ownerId, channelId }) {
  const w = findOwnerWorker(ownerId != null ? String(ownerId) : null, channelId);
  if (!w) {
    const e = new Error("no tienes ninguna reproducción activa");
    e.status = 404;
    throw e;
  }
  if (w.status === "loading") {
    const e = new Error("el video todavía está cargando, espera un momento");
    e.status = 409;
    throw e;
  }
  const hadQueue = w.queue.length > 0;
  const res = await autoAdvance(w, "siguiente");
  if (res) return { ...res, queued: false };
  return { stopped: true, had_queue: hadQueue };
}

// ----------------------------------------------------------------------------
// Player HTTP server (Firefox-facing, 127.0.0.1 only)
// ----------------------------------------------------------------------------
const playerHtml = fs.readFileSync(path.join(__dirname, "player.html"), "utf-8");

const playerServer = http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  if (url.pathname === "/" || url.pathname === "/index.html") {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(playerHtml);
    return;
  }
  const wIdx = url.searchParams.get("w");
  const worker =
    wIdx != null ? [...workers.values()].find((w) => String(w.index) === String(wIdx)) : null;
  if (url.pathname === "/ready") {
    res.writeHead(204).end();
    return;
  }
  if (url.pathname === "/playing") {
    worker?.onPlaying();
    res.writeHead(204).end();
    return;
  }
  if (url.pathname === "/ended") {
    worker?.onEnded();
    res.writeHead(204).end();
    return;
  }
  if (url.pathname === "/error") {
    worker?.onError(url.searchParams.get("reason"));
    res.writeHead(204).end();
    return;
  }
  res.writeHead(404).end();
});

// ----------------------------------------------------------------------------
// Control HTTP server (bot-facing, bearer-authenticated)
// ----------------------------------------------------------------------------
function send(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => {
      if (!data) return resolve({});
      try {
        resolve(JSON.parse(data));
      } catch {
        resolve({});
      }
    });
    req.on("error", () => resolve({}));
  });
}

function authorized(req) {
  if (!MANAGER_SECRET) return true;
  const h = req.headers["authorization"] || "";
  return h === `Bearer ${MANAGER_SECRET}`;
}

const controlServer = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://localhost");
    const parts = url.pathname.split("/").filter(Boolean);

    if (url.pathname === "/health") {
      const list = [...workers.values()];
      return send(res, 200, {
        ok: true,
        max_workers: MAX_WORKERS,
        workers: list.length,
        idle: list.filter((w) => w.status === "idle").length,
        busy: list.filter((w) => w.busy).length,
        queued: list.reduce((n, w) => n + w.queue.length, 0),
        quality,
      });
    }

    if (!authorized(req)) return send(res, 401, { detail: "no autorizado" });

    // GET /workers
    if (req.method === "GET" && url.pathname === "/workers") {
      return send(res, 200, { workers: [...workers.values()].map((w) => w.toJSON()) });
    }

    // POST /workers {token}
    if (req.method === "POST" && url.pathname === "/workers") {
      const body = await readBody(req);
      const w = await addWorker(body.token);
      return send(res, 200, w);
    }

    // DELETE /workers/:id
    if (req.method === "DELETE" && parts[0] === "workers" && parts[1]) {
      const r = await removeWorker(parts[1]);
      return send(res, 200, r);
    }

    // POST /workers/:id/stop
    if (req.method === "POST" && parts[0] === "workers" && parts[1] && parts[2] === "stop") {
      const w = workers.get(parts[1]);
      if (!w) return send(res, 404, { detail: "worker no encontrado" });
      return send(res, 200, await w.stop("stop API"));
    }

    // POST /play {guildId, channelId, video, workerId?}
    if (req.method === "POST" && url.pathname === "/play") {
      const body = await readBody(req);
      const r = await play(body);
      return send(res, 200, r);
    }

    // POST /stop {channelId?, ownerId?}  — detiene workers (por dueño o canal)
    if (req.method === "POST" && url.pathname === "/stop") {
      const body = await readBody(req);
      const ownerId = body.ownerId != null ? String(body.ownerId) : null;
      const stopped = [];
      for (const w of workers.values()) {
        if (ownerId) {
          if (w.ownerId !== ownerId) continue;
        } else {
          if (!w.busy) continue;
          if (body.channelId && w.current?.channelId !== String(body.channelId)) continue;
        }
        w.queue = [];
        await w.stop("stop API").catch(() => {});
        w.ownerId = null;
        w.ownerName = null;
        stopped.push(w.userId);
      }
      return send(res, 200, { stopped });
    }

    // POST /next {ownerId?, channelId?}  — salta al siguiente video de la cola
    if (req.method === "POST" && url.pathname === "/next") {
      const body = await readBody(req);
      const r = await nextFor(body);
      return send(res, 200, r);
    }

    // PUT /quality {width,height,fps,bitrate,bitrateMax}
    if (req.method === "PUT" && url.pathname === "/quality") {
      const body = await readBody(req);
      quality = { ...quality, ...sanitizeQuality(body) };
      for (const w of workers.values()) w.quality = quality;
      return send(res, 200, { quality });
    }

    return send(res, 404, { detail: "ruta no encontrada" });
  } catch (err) {
    const status = err?.status || 500;
    send(res, status, { detail: err?.message || "error interno" });
  }
});

function sanitizeQuality(b) {
  const out = {};
  const num = (v, lo, hi, d) => {
    const n = parseInt(v, 10);
    return Number.isFinite(n) ? Math.max(lo, Math.min(hi, n)) : d;
  };
  if (b.width != null) out.width = num(b.width, 320, 1920, quality.width);
  if (b.height != null) out.height = num(b.height, 240, 1080, quality.height);
  if (b.fps != null) out.fps = num(b.fps, 10, 60, quality.fps);
  if (b.bitrate != null) out.bitrate = num(b.bitrate, 500, 8000, quality.bitrate);
  if (b.bitrateMax != null) out.bitrateMax = num(b.bitrateMax, 500, 12000, quality.bitrateMax);
  if (b.audioOffset != null) {
    const f = parseFloat(b.audioOffset);
    out.audioOffset = Number.isFinite(f) ? Math.max(0, Math.min(3, f)) : quality.audioOffset;
  }
  return out;
}

// ----------------------------------------------------------------------------
// Boot
// ----------------------------------------------------------------------------
async function main() {
  await new Promise((r) => playerServer.listen(HTTP_PORT, "127.0.0.1", r));
  log(`player server on 127.0.0.1:${HTTP_PORT}`);
  await new Promise((r) => controlServer.listen(MANAGER_PORT, "0.0.0.0", r));
  log(`control API on 0.0.0.0:${MANAGER_PORT} (auth ${MANAGER_SECRET ? "on" : "OFF"})`);
  const totalGb = (os.totalmem() / (1024 ** 3)).toFixed(1);
  const mode = process.env.MAX_WORKERS && process.env.MAX_WORKERS.trim() ? "fijo" : "auto";
  log(`max workers: ${MAX_WORKERS} (${mode}, RAM total ${totalGb}GB, ~${PER_WORKER_MB}MB/worker)`);
}

async function shutdown(sig) {
  log("shutting down:", sig);
  for (const w of workers.values()) {
    await w.destroy().catch(() => {});
  }
  process.exit(0);
}
process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

main().catch((e) => {
  console.error("fatal:", e?.stack || e);
  process.exit(1);
});
