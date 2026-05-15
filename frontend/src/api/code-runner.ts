import { apiFetch } from './helpers';

const BASE = '/api/plugins/code-runner';

export interface CodeRunnerConfig {
  trigger_channel_id: string | null;
  lobby_message_id: string | null;
  enabled: boolean;
  allowed_languages: string[];
  max_code_chars: number;
  max_output_chars: number;
  exec_timeout_seconds: number;
  session_timeout_minutes: number;
  cooldown_seconds: number;
  max_infractions: number;
  security_model: string;
  security_enabled: boolean;
  mod_role_names: string[];
  category_id: string | null;
  piston_url: string;
}

export type CodeRunnerConfigPatch = Partial<CodeRunnerConfig>;

export interface CodeRunnerStatus {
  enabled: boolean;
  ready: boolean;
  expired_pending: number;
}

export interface CodeRunnerSession {
  id: number;
  user_id: string;
  guild_id: string;
  channel_id: string;
  status: string;
  created_at: number;
  expires_at: number;
  closed_at?: number | null;
  transcript_path?: string | null;
}

export interface CodeRunnerExecution {
  id: number;
  session_id: number | null;
  user_id: string;
  language: string;
  code: string;
  stdout: string;
  stderr: string;
  exit_code: string;
  status: string;
  created_at: number;
  warnings: string[];
  security: { malicious?: boolean; severity?: string; reasons?: string[] };
  analysis: { purpose?: string; improvements?: string[] };
}

export interface CodeRunnerStats {
  totals?: {
    executions_total?: number;
    sessions_total?: number;
    users_with_infractions?: number;
    infractions_total?: number;
  };
  executions_by_status: Record<string, number>;
  sessions_by_status: Record<string, number>;
  languages: { language: string; total: number }[];
  most_used_language: string | null;
  top_users: { user_id: string; executions: number }[];
}

export interface CodeRunnerDiscordChannel {
  id: string;
  name: string;
  guild_name: string;
}

export interface CodeRunnerDiscordRole {
  id: string;
  name: string;
  guild_name: string;
}

export async function fetchCodeRunnerConfig(): Promise<CodeRunnerConfig> {
  const res = await apiFetch(`${BASE}/config`);
  if (!res.ok) throw new Error(`Error al cargar configuración (${res.status})`);
  return (await res.json()) as CodeRunnerConfig;
}

export async function updateCodeRunnerConfig(patch: CodeRunnerConfigPatch): Promise<CodeRunnerConfig> {
  const res = await apiFetch(`${BASE}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Error al guardar (${res.status})`);
  }
  return (await res.json()) as CodeRunnerConfig;
}

export async function fetchCodeRunnerStatus(): Promise<CodeRunnerStatus> {
  const res = await apiFetch(`${BASE}/status`);
  if (!res.ok) throw new Error(`Error al consultar estado (${res.status})`);
  return (await res.json()) as CodeRunnerStatus;
}

export async function fetchCodeRunnerSessions(opts: { status?: string; limit?: number } = {}): Promise<CodeRunnerSession[]> {
  const params = new URLSearchParams();
  if (opts.status) params.set('status', opts.status);
  if (opts.limit) params.set('limit', String(opts.limit));
  const url = params.toString() ? `${BASE}/sessions?${params}` : `${BASE}/sessions`;
  const res = await apiFetch(url);
  if (!res.ok) throw new Error(`Error al cargar sesiones (${res.status})`);
  const data = (await res.json()) as { sessions: CodeRunnerSession[] };
  return data.sessions;
}

export async function fetchCodeRunnerExecutions(limit = 20): Promise<CodeRunnerExecution[]> {
  const res = await apiFetch(`${BASE}/executions?limit=${limit}`);
  if (!res.ok) throw new Error(`Error al cargar ejecuciones (${res.status})`);
  const data = (await res.json()) as { executions: CodeRunnerExecution[] };
  return data.executions;
}

export async function fetchCodeRunnerStats(): Promise<CodeRunnerStats> {
  const res = await apiFetch(`${BASE}/stats`);
  if (!res.ok) throw new Error(`Error al cargar stats (${res.status})`);
  return (await res.json()) as CodeRunnerStats;
}

export async function fetchCodeRunnerChannels(): Promise<CodeRunnerDiscordChannel[]> {
  const res = await apiFetch(`${BASE}/discord-channels`);
  if (!res.ok) throw new Error(`Error al cargar canales (${res.status})`);
  const data = (await res.json()) as { channels: CodeRunnerDiscordChannel[] };
  return data.channels;
}

export async function fetchCodeRunnerRoles(): Promise<CodeRunnerDiscordRole[]> {
  const res = await apiFetch(`${BASE}/discord-roles`);
  if (!res.ok) throw new Error(`Error al cargar roles (${res.status})`);
  const data = (await res.json()) as { roles: CodeRunnerDiscordRole[] };
  return data.roles;
}

export async function republishLobby(): Promise<{ published: boolean; action?: string; reason?: string }> {
  const res = await apiFetch(`${BASE}/trigger-channel/republish`);
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Error al republicar lobby (${res.status})`);
  }
  return (await res.json()) as { published: boolean; action?: string; reason?: string };
}

export async function closeSession(sessionId: number): Promise<{ closed: boolean; deleted: boolean }> {
  const res = await apiFetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Error al cerrar sesión (${res.status})`);
  }
  return (await res.json()) as { closed: boolean; deleted: boolean };
}

export const SUPPORTED_LANGUAGES = [
  { id: 'python', label: 'Python', short: 'PY' },
  { id: 'javascript', label: 'JavaScript', short: 'JS' },
  { id: 'typescript', label: 'TypeScript', short: 'TS' },
  { id: 'bash', label: 'Bash', short: 'SH' },
  { id: 'rust', label: 'Rust', short: 'RS' },
  { id: 'go', label: 'Go', short: 'GO' },
  { id: 'java', label: 'Java', short: 'JV' },
  { id: 'cpp', label: 'C++', short: 'C++' },
  { id: 'c', label: 'C', short: 'C' },
  { id: 'ruby', label: 'Ruby', short: 'RB' },
  { id: 'php', label: 'PHP', short: 'PHP' },
];
