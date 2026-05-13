import { apiFetch } from './helpers';

export interface ActivityEvent {
  id: number;
  ts: string;
  kind: 'welcome' | 'blackboard' | 'youtube' | 'config' | 'scrape' | 'system';
  title: string;
  detail: string;
  meta: Record<string, unknown>;
}

export async function fetchActivity(limit = 30): Promise<ActivityEvent[]> {
  const res = await apiFetch(`/api/activity?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = (await res.json()) as { items: ActivityEvent[] };
  return data.items;
}
