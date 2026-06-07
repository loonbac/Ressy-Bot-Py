import { apiFetch } from './helpers';

export const ALL_COMMANDS: string[] = ['ver', 'parar'];

export interface VideoConfig {
  enabled: boolean;
  manager_url: string;
  width: number;
  height: number;
  fps: number;
  bitrate: number;
  bitrate_max: number;
  enabled_commands: string[];
}

export interface VideoWorker {
  user_id: string;
  username: string;
  tag: string;
  avatar_url: string;
  status: string; // idle | playing | error | offline | unknown
  busy: boolean;
  token_preview: string;
  added_at?: string;
}

export interface VideoManagerStatus {
  online: boolean;
  max_workers?: number;
  workers?: number;
  idle?: number;
  busy?: number;
  detail?: string;
  quality?: { width: number; height: number; fps: number; bitrate: number; bitrateMax: number };
}

const DEFAULTS: VideoConfig = {
  enabled: true,
  manager_url: 'http://video-worker:8081',
  width: 1280,
  height: 720,
  fps: 30,
  bitrate: 3000,
  bitrate_max: 4500,
  enabled_commands: [...ALL_COMMANDS],
};

function normalize(raw: Partial<VideoConfig> | null | undefined): VideoConfig {
  const merged = { ...DEFAULTS, ...(raw ?? {}) } as VideoConfig;
  if (!Array.isArray(merged.enabled_commands)) {
    merged.enabled_commands = [...ALL_COMMANDS];
  }
  for (const k of ['width', 'height', 'fps', 'bitrate', 'bitrate_max'] as const) {
    if (typeof merged[k] !== 'number' || Number.isNaN(merged[k])) {
      merged[k] = DEFAULTS[k];
    }
  }
  return merged;
}

async function readDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    return data?.detail ?? '';
  } catch {
    return '';
  }
}

export async function fetchVideoConfig(): Promise<VideoConfig> {
  const res = await apiFetch('/api/plugins/videos/config');
  if (!res.ok) throw new Error(`Error al cargar configuración: ${res.status}`);
  return normalize((await res.json()) as Partial<VideoConfig>);
}

export async function updateVideoConfig(patch: Partial<VideoConfig>): Promise<VideoConfig> {
  const res = await apiFetch('/api/plugins/videos/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = await readDetail(res);
    throw new Error(detail || `Error al guardar: ${res.status}`);
  }
  return normalize((await res.json()) as Partial<VideoConfig>);
}

export async function fetchVideoWorkers(): Promise<{ workers: VideoWorker[]; manager_online: boolean }> {
  const res = await apiFetch('/api/plugins/videos/workers');
  if (!res.ok) throw new Error(`Error al cargar workers: ${res.status}`);
  const data = (await res.json()) as { workers: VideoWorker[]; manager_online: boolean };
  return { workers: data.workers ?? [], manager_online: Boolean(data.manager_online) };
}

export async function addVideoWorker(token: string): Promise<VideoWorker> {
  const res = await apiFetch('/api/plugins/videos/workers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) {
    const detail = await readDetail(res);
    throw new Error(detail || `No se pudo agregar el worker: ${res.status}`);
  }
  return res.json() as Promise<VideoWorker>;
}

export async function deleteVideoWorker(userId: string): Promise<void> {
  const res = await apiFetch(`/api/plugins/videos/workers/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const detail = await readDetail(res);
    throw new Error(detail || `No se pudo eliminar el worker: ${res.status}`);
  }
}

export async function stopVideoWorker(userId: string): Promise<void> {
  const res = await apiFetch(`/api/plugins/videos/workers/${encodeURIComponent(userId)}/stop`, {
    method: 'POST',
  });
  if (!res.ok) {
    const detail = await readDetail(res);
    throw new Error(detail || `No se pudo detener el worker: ${res.status}`);
  }
}

export async function fetchVideoStatus(): Promise<VideoManagerStatus> {
  const res = await apiFetch('/api/plugins/videos/status');
  if (!res.ok) return { online: false, detail: `Error ${res.status}` };
  return res.json() as Promise<VideoManagerStatus>;
}
