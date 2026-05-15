import { apiFetch } from './helpers';

const BASE = '/api/plugins/openrouter-prices';

// ----------------------------------------------------------------
// Tipos
// ----------------------------------------------------------------

export interface ScrapeHealth {
  last_started_at: number | null;
  last_finished_at: number | null;
  last_status: string | null;
  last_error: string | null;
  age_seconds: number | null;
  stale: boolean;
}

export interface OpenRouterStatus {
  enabled: boolean;
  models_count: number;
  last_fetched_at: number | null;
  scrape_health?: Record<string, ScrapeHealth>;
  warnings?: string[];
}

export interface OpenRouterConfig {
  enabled: boolean;
  ttl_seconds: number;
  max_models_command: number;
  discord_channel_id: string | null;
  ranking_phase: string;
  phases_enabled: string[];
  ranking_embed_per_phase: boolean;
  aa_api_key: string;
  stale_threshold_days: number;
  github_token?: string;
  bfcl_scrape_max_models?: number;
  [key: string]: unknown;
}

export interface OpenRouterModel {
  id: string;
  name: string;
  pricing_prompt_per_mtok: number | null;
  pricing_completion_per_mtok: number | null;
  context_length: number | null;
  modalities: string[];
  provider?: string;
  is_text_only?: boolean;
  is_free?: boolean;
}

export interface PhaseSummary {
  slug: string;
  label: string;
  description: string;
  weights_count: number;
  active_benchmarks_count: number;
  reserved_benchmarks_count: number;
  feature_factors_count: number;
  last_ranking_computed_at: number | null;
}

export interface RankingEntry {
  rank: number;
  model_id: string;
  model_name: string;
  score: number;
  breakdown?: Record<string, { raw: number; normalized: number; contribution: number }>;
  pricing_prompt_per_mtok?: number | null;
  pricing_completion_per_mtok?: number | null;
}

export interface RankingResponse {
  phase: string;
  entries: RankingEntry[];
  computed_at: number | null;
}

export interface AliasEntry {
  openrouter_id: string;
  source: string;
  external_name: string;
  score?: number;
  created_at?: number | null;
}

export interface ScrapeRun {
  id?: number;
  source: string;
  started_at: number;
  finished_at: number | null;
  status: string;
  error: string | null;
  rows_updated: number;
  aliases_missed?: number;
}

export interface BenchmarkRow {
  slug: string;
  description: string;
  source: string;
  direction: string;
  is_feature_factor?: boolean;
  reserved?: boolean;
  used_by_phases?: number;
}

export interface DiscordChannel {
  id: string;
  name: string;
  guild_name: string;
}

// ----------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail = '';
    try {
      const data = await res.json();
      detail = data?.detail ?? '';
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Error ${res.status} en ${path}`);
  }
  return res.json() as Promise<T>;
}

// ----------------------------------------------------------------
// Status + config
// ----------------------------------------------------------------

export function fetchOpenRouterStatus(): Promise<OpenRouterStatus> {
  return json<OpenRouterStatus>('/status');
}

export async function fetchOpenRouterConfig(): Promise<OpenRouterConfig> {
  const raw = await json<Record<string, unknown>>('/config');
  return normalizeConfig(raw);
}

export async function updateOpenRouterConfig(
  patch: Partial<OpenRouterConfig>,
): Promise<OpenRouterConfig> {
  const payload: Record<string, unknown> = { ...patch };
  if (Array.isArray(patch.phases_enabled)) {
    payload.phases_enabled = JSON.stringify(patch.phases_enabled);
  }
  const raw = await json<Record<string, unknown>>('/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return normalizeConfig(raw);
}

function normalizeConfig(raw: Record<string, unknown>): OpenRouterConfig {
  const enabled = raw.enabled === true || raw.enabled === 'true';
  const ranking_embed_per_phase =
    raw.ranking_embed_per_phase === true || raw.ranking_embed_per_phase === 'true';
  let phases_enabled: string[] = [];
  const rawPhases = raw.phases_enabled;
  if (Array.isArray(rawPhases)) {
    phases_enabled = rawPhases.map(String);
  } else if (typeof rawPhases === 'string' && rawPhases.length > 0) {
    try {
      const parsed = JSON.parse(rawPhases);
      if (Array.isArray(parsed)) {
        phases_enabled = parsed.map(String);
      }
    } catch {
      phases_enabled = rawPhases.split(',').map((s) => s.trim()).filter(Boolean);
    }
  }
  return {
    enabled,
    ttl_seconds: Number(raw.ttl_seconds ?? 3600),
    max_models_command: Number(raw.max_models_command ?? 10),
    discord_channel_id:
      typeof raw.discord_channel_id === 'string' && raw.discord_channel_id.length > 0
        ? raw.discord_channel_id
        : null,
    ranking_phase: String(raw.ranking_phase ?? 'orchestrator'),
    phases_enabled,
    ranking_embed_per_phase,
    aa_api_key: String(raw.aa_api_key ?? ''),
    stale_threshold_days: Number(raw.stale_threshold_days ?? 14),
    github_token: String(raw.github_token ?? ''),
    bfcl_scrape_max_models: Number(raw.bfcl_scrape_max_models ?? 200),
    ...raw,
  } as OpenRouterConfig;
}

// ----------------------------------------------------------------
// Models
// ----------------------------------------------------------------

export interface FetchModelsParams {
  limit?: number;
  offset?: number;
  text_only?: boolean;
  sort_by?: 'prompt' | 'completion' | 'name' | 'context';
  sort_dir?: 'asc' | 'desc';
  search?: string;
}

export async function fetchOpenRouterModels(
  params: FetchModelsParams = {},
): Promise<{ models: OpenRouterModel[]; total: number }> {
  const query = new URLSearchParams();
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset) query.set('offset', String(params.offset));
  if (params.text_only) query.set('text_only', 'true');
  if (params.sort_by) query.set('sort_by', params.sort_by);
  if (params.sort_dir) query.set('sort_dir', params.sort_dir);
  if (params.search) query.set('search', params.search);
  const qs = query.toString();
  const raw = await json<{ models?: OpenRouterModel[]; total?: number } | OpenRouterModel[]>(
    `/models${qs ? `?${qs}` : ''}`,
  );
  if (Array.isArray(raw)) {
    return { models: raw, total: raw.length };
  }
  return {
    models: raw.models ?? [],
    total: raw.total ?? raw.models?.length ?? 0,
  };
}

export async function refreshOpenRouterCatalog(): Promise<{ count: number }> {
  return json<{ count: number }>('/refresh', { method: 'POST' });
}

// ----------------------------------------------------------------
// Phases + rankings
// ----------------------------------------------------------------

export function fetchPhases(): Promise<PhaseSummary[]> {
  return json<PhaseSummary[]>('/phases');
}

export function fetchPhaseRanking(phase: string, n = 10): Promise<RankingResponse> {
  return json<RankingResponse>(`/rankings/${phase}?n=${n}`);
}

export interface PhaseWeightEntry {
  benchmark_slug: string;
  weight: number;
  is_feature_factor: boolean;
}

export function fetchPhaseWeights(phase: string): Promise<PhaseWeightEntry[]> {
  // Reusa endpoint existente que devuelve get_phase_profile
  return json<PhaseWeightEntry[]>(`/phases/${phase}/weights`).catch(async () => {
    // Fallback: si endpoint no existe, derivar de rankings/breakdown
    return [];
  });
}

export async function triggerRankingEmbed(
  phase: string,
): Promise<{ phase: string; channel_id: string; models_published: number }> {
  return json<{ phase: string; channel_id: string; models_published: number }>(
    `/embed/ranking/${phase}`,
    { method: 'POST' },
  );
}

export async function updatePhaseWeights(
  phase: string,
  weights: PhaseWeightEntry[],
): Promise<{ phase: string; weights_count: number; sum: number }> {
  return json<{ phase: string; weights_count: number; sum: number }>(
    `/phases/${phase}/weights`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ weights }),
    },
  );
}

// ----------------------------------------------------------------
// Scrapers
// ----------------------------------------------------------------

export async function triggerScrape(source: string): Promise<{ status: string }> {
  return json<{ status: string }>(`/scrape/${source}`, { method: 'POST' });
}

export function fetchScrapeRuns(
  limit = 20,
  source?: string,
): Promise<{ runs: ScrapeRun[] } | ScrapeRun[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (source) query.set('source', source);
  return json<{ runs: ScrapeRun[] } | ScrapeRun[]>(`/scrape-runs?${query.toString()}`);
}

// ----------------------------------------------------------------
// Aliases
// ----------------------------------------------------------------

export async function fetchAliases(): Promise<AliasEntry[]> {
  const raw = await json<{ aliases?: AliasEntry[] } | AliasEntry[]>('/aliases');
  if (Array.isArray(raw)) return raw;
  return raw.aliases ?? [];
}

export async function putAlias(
  openrouter_id: string,
  body: { source: string; external_name: string },
): Promise<AliasEntry> {
  return json<AliasEntry>(`/aliases/${encodeURIComponent(openrouter_id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// ----------------------------------------------------------------
// Benchmarks
// ----------------------------------------------------------------

export async function fetchBenchmarks(): Promise<BenchmarkRow[]> {
  const raw = await json<{ benchmarks?: BenchmarkRow[] } | BenchmarkRow[]>('/benchmarks');
  if (Array.isArray(raw)) return raw;
  return raw.benchmarks ?? [];
}

// ----------------------------------------------------------------
// Discord channels
// ----------------------------------------------------------------

export async function fetchOpenRouterDiscordChannels(): Promise<DiscordChannel[]> {
  const raw = await json<{ channels?: DiscordChannel[] }>('/discord-channels');
  return raw.channels ?? [];
}
