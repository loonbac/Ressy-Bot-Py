import { ConfigResponse, BotStatus } from '@/types';
import { apiFetch } from './helpers';

export async function fetchConfig(): Promise<ConfigResponse[]> {
  const res = await apiFetch('/api/config');
  if (!res.ok) {
    throw new Error(`Failed to fetch config: ${res.status}`);
  }
  const data = (await res.json()) as { configs: ConfigResponse[] };
  return data.configs;
}

export async function updateConfig(
  key: string,
  value: unknown
): Promise<ConfigResponse> {
  const res = await apiFetch(`/api/config/${encodeURIComponent(key)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to update config: ${res.status} ${err}`);
  }
  return res.json() as Promise<ConfigResponse>;
}

export async function fetchStatus(): Promise<BotStatus> {
  const res = await apiFetch('/api/status');
  if (!res.ok) {
    throw new Error(`Failed to fetch status: ${res.status}`);
  }
  return res.json() as Promise<BotStatus>;
}
