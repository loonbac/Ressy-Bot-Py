import { apiFetch } from './helpers';

export interface YouTubeSubscription {
  channel_id: string;
  channel_name: string;
  thumbnail_url: string;
  added_at: string;
  last_checked: string | null;
  active: boolean;
  notifications_enabled: boolean;
  last_video_title?: string | null;
  last_video_url?: string | null;
  video_count?: number;
}

export interface YouTubeConfig {
  enabled: boolean;
  poll_interval_minutes: number;
  // Discord snowflake — string to preserve 64-bit precision across the JSON boundary
  discord_channel_id: string | null;
  callback_url: string;
  google_api_key: string;
  announcement_message: string;
  filter_shorts: boolean;
  filter_premieres: boolean;
  filter_min_duration: number;
}

export interface DiscordChannel {
  // Discord snowflake — string to preserve 64-bit precision
  id: string;
  name: string;
  guild_name: string;
}

export async function fetchYouTubeSubscriptions(): Promise<YouTubeSubscription[]> {
  const res = await apiFetch('/api/plugins/youtube/subscriptions');
  if (!res.ok) {
    throw new Error(`Failed to fetch subscriptions: ${res.status}`);
  }
  const data = (await res.json()) as { subscriptions: YouTubeSubscription[] };
  return data.subscriptions;
}

export async function addYouTubeSubscription(channelId: string, channelName?: string, thumbnailUrl?: string): Promise<YouTubeSubscription> {
  const res = await apiFetch('/api/plugins/youtube/subscriptions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel_id: channelId, channel_name: channelName || '', thumbnail_url: thumbnailUrl || '' }),
  });
  if (!res.ok) {
    throw new Error(`Failed to add subscription: ${res.status}`);
  }
  return res.json() as Promise<YouTubeSubscription>;
}

export async function removeYouTubeSubscription(channelId: string): Promise<void> {
  const res = await apiFetch(`/api/plugins/youtube/subscriptions/${encodeURIComponent(channelId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to remove subscription: ${res.status}`);
  }
}

export async function toggleYouTubeNotifications(channelId: string, enabled: boolean): Promise<void> {
  const res = await apiFetch(`/api/plugins/youtube/subscriptions/${encodeURIComponent(channelId)}/notifications`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) {
    throw new Error(`Failed to toggle notifications: ${res.status}`);
  }
}

export async function fetchYouTubeConfig(): Promise<YouTubeConfig> {
  const res = await apiFetch('/api/plugins/youtube/config');
  if (!res.ok) {
    throw new Error(`Failed to fetch YouTube config: ${res.status}`);
  }
  return res.json() as Promise<YouTubeConfig>;
}

export async function updateYouTubeConfig(config: Partial<YouTubeConfig>): Promise<YouTubeConfig> {
  const res = await apiFetch('/api/plugins/youtube/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    throw new Error(`Failed to update YouTube config: ${res.status}`);
  }
  return res.json() as Promise<YouTubeConfig>;
}

export interface YouTubeSearchResult {
  channel_id: string;
  channel_name: string;
  description: string;
  thumbnail: string;
}

export function getProxiedThumbnailUrl(thumbnailUrl: string): string {
  return `/api/plugins/youtube/thumbnail?url=${encodeURIComponent(thumbnailUrl)}`;
}

export async function searchYouTubeChannels(query: string): Promise<YouTubeSearchResult[]> {
  const res = await apiFetch(`/api/plugins/youtube/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) {
    throw new Error(`Failed to search: ${res.status}`);
  }
  const data = (await res.json()) as { results: YouTubeSearchResult[] };
  return data.results;
}

export async function fetchDiscordChannels(): Promise<DiscordChannel[]> {
  const res = await apiFetch('/api/plugins/youtube/discord-channels');
  if (!res.ok) {
    throw new Error(`Failed to fetch Discord channels: ${res.status}`);
  }
  const data = (await res.json()) as { channels: DiscordChannel[] };
  return data.channels;
}

export interface PollDiagnostics {
  channel_id: string;
  channel_name: string;
  status: 'ok' | 'error';
  videos_found?: number;
  new_videos?: number;
  error?: string;
  error_detail?: string;
}

export async function triggerYouTubePoll(): Promise<{
  new_videos: number;
  has_api_key: boolean;
  diagnostics: PollDiagnostics[];
  channels_checked: number;
  videos: any[];
}> {
  const res = await apiFetch('/api/plugins/youtube/poll', { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to trigger poll: ${res.status}`);
  return res.json() as Promise<{
    new_videos: number;
    has_api_key: boolean;
    diagnostics: PollDiagnostics[];
    channels_checked: number;
    videos: any[];
  }>;
}

export async function removeFailedSubscriptions(): Promise<{ removed: string[]; count: number }> {
  const res = await apiFetch('/api/plugins/youtube/subscriptions/failed', { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to clean: ${res.status}`);
  return res.json() as Promise<{ removed: string[]; count: number }>;
}

export interface TestNotifyDiagnostics {
  channel_id: string;
  channel_name: string;
  status: 'ok' | 'error';
  videos_sent?: number;
  error?: string;
  error_detail?: string;
}

export interface TestNotifyResult {
  total_sent: number;
  has_api_key: boolean;
  channels_checked: number;
  diagnostics: TestNotifyDiagnostics[];
}

export async function testNotifyLatest(count: number): Promise<TestNotifyResult> {
  const res = await apiFetch('/api/plugins/youtube/test-notify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ count }),
  });
  if (!res.ok) {
    let detail = '';
    try {
      const data = await res.json();
      detail = data?.detail ?? '';
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Failed to test-notify: ${res.status}`);
  }
  return res.json() as Promise<TestNotifyResult>;
}
