import { apiFetch } from './helpers';

export interface BlackboardConfig {
  enabled: boolean;
  blackboard_url: string;
  blackboard_user: string;
  blackboard_pass: string;
  // Discord snowflake as string to preserve 64-bit precision
  discord_channel_id: string | null;
  mention_role_id: string | null;
  poll_interval_minutes: number;
  weekly_digest_day: number;
  timezone: string;
  headless: boolean;
}

export interface BlackboardDiscordChannel {
  id: string;
  name: string;
  guild_name: string;
}

export interface BlackboardDiscordRole {
  id: string;
  name: string;
  color: number;
  guild_name: string;
}

export interface PendingResult {
  sent: boolean;
  channel_id: string;
  channel_name: string;
  pending_count: number;
  mention_role_id: string | null;
}

export interface BlackboardAssignment {
  id: number;
  assignment_id: string;
  title: string;
  course_name: string;
  course_id: string;
  due_date: string | null;
  status: string;
  source_url: string;
  created_at?: string;
  updated_at?: string;
}

export interface ScrapeStep {
  ts: string;
  elapsed_s: number;
  level: string;
  message: string;
}

export interface ScrapeResult {
  assignments_found: number;
  new_assignments: number;
  steps?: ScrapeStep[];
}

export async function fetchScrapeStatus(): Promise<{ steps: ScrapeStep[]; count: number }> {
  const res = await apiFetch('/api/plugins/blackboard/scrape-status');
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json() as Promise<{ steps: ScrapeStep[]; count: number }>;
}

const DEFAULTS: BlackboardConfig = {
  enabled: true,
  blackboard_url: 'https://senati.blackboard.com',
  blackboard_user: '',
  blackboard_pass: '',
  discord_channel_id: null,
  mention_role_id: null,
  poll_interval_minutes: 60,
  weekly_digest_day: 0,
  timezone: 'America/Lima',
  headless: true,
};

function normalize(raw: Partial<BlackboardConfig> | null | undefined): BlackboardConfig {
  const merged = { ...DEFAULTS, ...(raw ?? {}) };
  if (typeof merged.poll_interval_minutes !== 'number' || Number.isNaN(merged.poll_interval_minutes)) {
    merged.poll_interval_minutes = DEFAULTS.poll_interval_minutes;
  }
  if (typeof merged.weekly_digest_day !== 'number' || Number.isNaN(merged.weekly_digest_day)) {
    merged.weekly_digest_day = DEFAULTS.weekly_digest_day;
  }
  // Backend may send IDs as number — coerce to string for precision
  const rawObj = raw as Record<string, unknown> | undefined;
  if (rawObj) {
    const ch = rawObj.discord_channel_id;
    if (ch !== undefined && ch !== null) merged.discord_channel_id = String(ch);
    const rl = rawObj.mention_role_id;
    if (rl !== undefined && rl !== null) merged.mention_role_id = String(rl);
  }
  return merged;
}

export async function fetchBlackboardConfig(): Promise<BlackboardConfig> {
  const res = await apiFetch('/api/plugins/blackboard/config');
  if (!res.ok) throw new Error(`Failed to fetch config: ${res.status}`);
  const data = (await res.json()) as Partial<BlackboardConfig>;
  return normalize(data);
}

export async function updateBlackboardConfig(
  cfg: Partial<BlackboardConfig>,
): Promise<BlackboardConfig> {
  const payload: Record<string, unknown> = { ...cfg };
  if (payload.discord_channel_id === '') payload.discord_channel_id = null;
  if (payload.mention_role_id === '') payload.mention_role_id = null;
  const res = await apiFetch('/api/plugins/blackboard/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = '';
    try {
      const d = await res.json();
      detail = d?.detail ?? '';
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Failed to update config: ${res.status}`);
  }
  const data = (await res.json()) as Partial<BlackboardConfig>;
  return normalize(data);
}

export async function fetchBlackboardChannels(): Promise<BlackboardDiscordChannel[]> {
  const res = await apiFetch('/api/plugins/blackboard/discord-channels');
  if (!res.ok) throw new Error(`Failed to fetch channels: ${res.status}`);
  const data = (await res.json()) as { channels: BlackboardDiscordChannel[] };
  return data.channels;
}

export async function triggerBlackboardScrape(): Promise<ScrapeResult> {
  const res = await apiFetch('/api/plugins/blackboard/scrape', { method: 'POST' });
  if (!res.ok) {
    let detail = '';
    try {
      const d = await res.json();
      detail = d?.detail ?? '';
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Scrape failed: ${res.status}`);
  }
  return res.json() as Promise<ScrapeResult>;
}

export async function fetchBlackboardAssignments(): Promise<BlackboardAssignment[]> {
  const res = await apiFetch('/api/plugins/blackboard/assignments');
  if (!res.ok) throw new Error(`Failed to fetch assignments: ${res.status}`);
  const data = (await res.json()) as { assignments: BlackboardAssignment[] };
  return data.assignments;
}

export async function fetchBlackboardRoles(): Promise<BlackboardDiscordRole[]> {
  const res = await apiFetch('/api/plugins/blackboard/discord-roles');
  if (!res.ok) throw new Error(`Failed to fetch roles: ${res.status}`);
  const data = (await res.json()) as { roles: BlackboardDiscordRole[] };
  return data.roles;
}

export async function sendPendingDigest(): Promise<PendingResult> {
  const res = await apiFetch('/api/plugins/blackboard/send-pending', { method: 'POST' });
  if (!res.ok) {
    let detail = '';
    try {
      const d = await res.json();
      detail = d?.detail ?? '';
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Failed to send pending: ${res.status}`);
  }
  return res.json() as Promise<PendingResult>;
}
