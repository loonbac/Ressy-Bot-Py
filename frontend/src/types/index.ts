export interface ConfigResponse {
  key: string;
  value: unknown;
  updated_at: string;
}

export interface ConfigUpdate {
  key: string;
  value: unknown;
}

export interface WSMessage {
  event: 'config:updated' | 'config:deleted';
  key: string;
  value: unknown;
}

export interface BotStatus {
  online: boolean;
  uptime_seconds: number;
  loaded_cogs: string[];
  connected_ws_clients: number;
  latency_ms: number;
  memory_mb: number;
  bot_avatar_url: string;
  bot_name: string;
}
