import { apiFetch } from './helpers';

const BASE = '/api/plugins/linux-updates';

export interface LinuxProduct {
  slug: string;
  display_name: string;
  release_count: number;
  active_count: number;
  expiring_soon_count: number;
  last_check_at: number | null;
  last_check_status: 'ok' | 'error' | string;
  stale: boolean;
  updated_at: string;
}

export interface LinuxRelease {
  cycle: string;
  codename: string | null;
  release_date: string | null;
  eol_date: string | null;
  latest_version: string | null;
  lts: boolean;
  days_until_eol: number | null;
  status: 'active' | 'expired' | 'unknown';
}

export interface LinuxProductDetail {
  slug: string;
  display_name: string;
  last_check_at: number | null;
  last_check_status: string;
  releases: LinuxRelease[];
}

export interface LinuxSummary {
  total_releases: number;
  active_releases: number;
  expiring_soon: Array<{ slug: string; cycle: string; eol_date: string; days_left: number }>;
  expired: Array<{ slug: string; cycle: string; eol_date: string }>;
  no_eol_date: Array<{ slug: string; cycle: string; note: string }>;
}

export interface LinuxConfig {
  enabled: boolean;
  refresh_interval_hours: number;
  eol_warning_days: number;
  discord_channel_id: string;
}

export interface LinuxDiscordChannel {
  id: string;
  name: string;
  guild_name: string;
}

export interface LinuxRefreshResult {
  refreshed: number;
  failed: number;
  errors: Array<{ slug: string; error: string }>;
  skipped: boolean;
}

const DEFAULTS: LinuxConfig = {
  enabled: true,
  refresh_interval_hours: 12,
  eol_warning_days: 90,
  discord_channel_id: '',
};

function normalizeConfig(raw: Partial<LinuxConfig> | null | undefined): LinuxConfig {
  const merged = { ...DEFAULTS, ...(raw ?? {}) } as LinuxConfig;
  if (typeof merged.refresh_interval_hours !== 'number' || Number.isNaN(merged.refresh_interval_hours)) {
    merged.refresh_interval_hours = DEFAULTS.refresh_interval_hours;
  }
  if (typeof merged.eol_warning_days !== 'number' || Number.isNaN(merged.eol_warning_days)) {
    merged.eol_warning_days = DEFAULTS.eol_warning_days;
  }
  if (typeof merged.discord_channel_id !== 'string') {
    merged.discord_channel_id = '';
  }
  merged.enabled = Boolean(merged.enabled);
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

export async function fetchLinuxProducts(): Promise<LinuxProduct[]> {
  const res = await apiFetch(`${BASE}/products`);
  if (!res.ok) {
    throw new Error(`Error al cargar distribuciones: ${res.status}`);
  }
  return (await res.json()) as LinuxProduct[];
}

export async function fetchLinuxProduct(slug: string): Promise<LinuxProductDetail> {
  const res = await apiFetch(`${BASE}/products/${encodeURIComponent(slug)}`);
  if (!res.ok) {
    throw new Error(`Error al cargar producto ${slug}: ${res.status}`);
  }
  return (await res.json()) as LinuxProductDetail;
}

export async function fetchLinuxSummary(): Promise<LinuxSummary> {
  const res = await apiFetch(`${BASE}/summary`);
  if (!res.ok) {
    throw new Error(`Error al cargar resumen: ${res.status}`);
  }
  return (await res.json()) as LinuxSummary;
}

export async function fetchLinuxConfig(): Promise<LinuxConfig> {
  const res = await apiFetch(`${BASE}/config`);
  if (!res.ok) {
    throw new Error(`Error al cargar configuración: ${res.status}`);
  }
  return normalizeConfig((await res.json()) as Partial<LinuxConfig>);
}

export async function updateLinuxConfig(patch: Partial<LinuxConfig>): Promise<LinuxConfig> {
  const res = await apiFetch(`${BASE}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = await readDetail(res);
    throw new Error(detail || `Error al guardar configuración: ${res.status}`);
  }
  return normalizeConfig((await res.json()) as Partial<LinuxConfig>);
}

export async function refreshLinuxNow(): Promise<LinuxRefreshResult> {
  const res = await apiFetch(`${BASE}/refresh`, { method: 'POST' });
  if (!res.ok) {
    const detail = await readDetail(res);
    throw new Error(detail || `Error al refrescar: ${res.status}`);
  }
  return (await res.json()) as LinuxRefreshResult;
}

export async function fetchLinuxDiscordChannels(): Promise<LinuxDiscordChannel[]> {
  const res = await apiFetch(`${BASE}/discord-channels`);
  if (!res.ok) {
    throw new Error(`Error al cargar canales: ${res.status}`);
  }
  const data = (await res.json()) as { channels?: LinuxDiscordChannel[] };
  return data.channels ?? [];
}
