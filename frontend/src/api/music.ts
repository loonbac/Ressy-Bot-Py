import { apiFetch } from './helpers';

export type AudioQuality = 'standard' | 'medium' | 'high';

export interface MusicConfig {
  enabled: boolean;
  default_volume: number;
  audio_quality: AudioQuality;
  allowed_channel_ids: string[];
  enabled_commands: string[];
}

export interface MusicVoiceChannel {
  id: string;
  name: string;
  guild_name: string;
}

export interface MusicTrack {
  title: string;
  url: string;
  requester_id: string;
  requester_name: string;
  duration_seconds: number;
  thumbnail_url: string;
}

export interface MusicQueueResponse {
  guild_id: string;
  tracks: MusicTrack[];
  current_track: MusicTrack | null;
  length: number;
  total_duration_seconds: number;
  volume: number;
}

export interface MusicNowPlaying {
  current_track: MusicTrack | null;
  is_playing: boolean;
  is_paused: boolean;
  volume: number;
}

export const ALL_COMMANDS: string[] = ['play', 'stop', 'queue', 'nowplaying'];

const DEFAULTS: MusicConfig = {
  enabled: true,
  default_volume: 50,
  audio_quality: 'high',
  allowed_channel_ids: [],
  enabled_commands: [...ALL_COMMANDS],
};

function normalize(raw: Partial<MusicConfig> | null | undefined): MusicConfig {
  const merged = { ...DEFAULTS, ...(raw ?? {}) } as MusicConfig;
  if (!Array.isArray(merged.allowed_channel_ids)) {
    merged.allowed_channel_ids = [];
  }
  if (!Array.isArray(merged.enabled_commands)) {
    merged.enabled_commands = [...ALL_COMMANDS];
  }
  const legacyMap: Record<string, AudioQuality> = { zen: 'high' };
  const remapped = legacyMap[merged.audio_quality as string];
  if (remapped) merged.audio_quality = remapped;
  if (!['standard', 'medium', 'high'].includes(merged.audio_quality)) {
    merged.audio_quality = 'high';
  }
  if (typeof merged.default_volume !== 'number' || Number.isNaN(merged.default_volume)) {
    merged.default_volume = DEFAULTS.default_volume;
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

export async function fetchMusicConfig(): Promise<MusicConfig> {
  const res = await apiFetch('/api/plugins/music/config');
  if (!res.ok) {
    throw new Error(`Error al cargar configuración de música: ${res.status}`);
  }
  return normalize((await res.json()) as Partial<MusicConfig>);
}

export async function updateMusicConfig(patch: Partial<MusicConfig>): Promise<MusicConfig> {
  const res = await apiFetch('/api/plugins/music/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = await readDetail(res);
    throw new Error(detail || `Error al guardar configuración: ${res.status}`);
  }
  return normalize((await res.json()) as Partial<MusicConfig>);
}

export async function fetchMusicVoiceChannels(): Promise<MusicVoiceChannel[]> {
  const res = await apiFetch('/api/plugins/music/discord-channels');
  if (!res.ok) {
    throw new Error(`Error al cargar canales de voz: ${res.status}`);
  }
  const data = (await res.json()) as { channels: MusicVoiceChannel[] };
  return data.channels ?? [];
}

export async function fetchMusicNowPlaying(guildId: string): Promise<MusicNowPlaying> {
  const res = await apiFetch(
    `/api/plugins/music/nowplaying?guild_id=${encodeURIComponent(guildId)}`,
  );
  if (!res.ok) {
    throw new Error(`Error al consultar reproducción: ${res.status}`);
  }
  return res.json() as Promise<MusicNowPlaying>;
}

export async function fetchMusicQueue(guildId: string): Promise<MusicQueueResponse> {
  const res = await apiFetch(
    `/api/plugins/music/queue?guild_id=${encodeURIComponent(guildId)}`,
  );
  if (!res.ok) {
    throw new Error(`Error al consultar cola: ${res.status}`);
  }
  return res.json() as Promise<MusicQueueResponse>;
}
