import { apiFetch } from './helpers';

export interface WelcomeConfig {
  enabled: boolean;
  welcome_channel_id: string;
  welcome_message: string;
  embed_title: string;
  embed_color: number;
  welcome_image_url: string;
  dm_enabled: boolean;
  delete_previous: boolean;
}

export interface WelcomeDiscordChannel {
  id: string;
  name: string;
  guild_name: string;
}

const DEFAULTS: WelcomeConfig = {
  enabled: true,
  welcome_channel_id: '',
  welcome_message: '',
  embed_title: 'Bienvenid@ {user_name} a Korosoft Community',
  embed_color: 2326507,
  welcome_image_url: '',
  dm_enabled: false,
  delete_previous: false,
};

function normalize(raw: Partial<WelcomeConfig> | null | undefined): WelcomeConfig {
  const merged = { ...DEFAULTS, ...(raw ?? {}) };
  if (typeof merged.embed_color !== 'number' || Number.isNaN(merged.embed_color)) {
    merged.embed_color = DEFAULTS.embed_color;
  }
  return merged;
}

export async function fetchWelcomeConfig(): Promise<WelcomeConfig> {
  const res = await apiFetch('/api/plugins/welcome/config');
  if (!res.ok) {
    throw new Error(`Failed to fetch welcome config: ${res.status}`);
  }
  const data = (await res.json()) as Partial<WelcomeConfig>;
  return normalize(data);
}

export async function updateWelcomeConfig(
  patch: Partial<WelcomeConfig>,
): Promise<WelcomeConfig> {
  const res = await apiFetch('/api/plugins/welcome/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    throw new Error(`Failed to update welcome config: ${res.status}`);
  }
  const data = (await res.json()) as Partial<WelcomeConfig>;
  return normalize(data);
}

export async function fetchWelcomeDiscordChannels(): Promise<WelcomeDiscordChannel[]> {
  const res = await apiFetch('/api/plugins/welcome/discord-channels');
  if (!res.ok) {
    throw new Error(`Failed to fetch channels: ${res.status}`);
  }
  const data = (await res.json()) as { channels: WelcomeDiscordChannel[] };
  return data.channels;
}

export async function sendWelcomeTest(): Promise<{ sent: boolean; channel_id: string }> {
  const res = await apiFetch('/api/plugins/welcome/test', { method: 'POST' });
  if (!res.ok) {
    let detail = '';
    try {
      const data = await res.json();
      detail = data?.detail ?? '';
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Failed to send test: ${res.status}`);
  }
  return res.json() as Promise<{ sent: boolean; channel_id: string }>;
}
