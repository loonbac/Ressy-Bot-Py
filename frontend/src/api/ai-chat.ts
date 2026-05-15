import { apiFetch } from './helpers';

const BASE = '/api/plugins/ai-chat';

export interface AIChatConfig {
  enabled: boolean;
  chat_model: string;
  analysis_model: string;
  system_prompt: string;
  max_context_messages: number;
  rate_limit_seconds: number;
}

export type AIChatConfigPatch = Partial<AIChatConfig>;

export interface AIChatStatus {
  enabled: boolean;
  chat_model: string;
  ready: boolean;
}

export interface ChatRequest {
  user_id: string;
  channel_id?: string;
  message: string;
}

export interface ChatResponse {
  reply: string;
  thinking: string | null;
  chat_model: string;
  conversation_id: string;
}

export interface MinimaxModel {
  id: string;
  label: string;
}

export async function fetchMinimaxModels(): Promise<MinimaxModel[]> {
  const res = await apiFetch(`${BASE}/models`);
  if (!res.ok) throw new Error(`Error al cargar modelos (${res.status})`);
  const data = (await res.json()) as { models: MinimaxModel[]; count: number };
  return data.models;
}

export async function fetchAIChatConfig(): Promise<AIChatConfig> {
  const res = await apiFetch(`${BASE}/config`);
  if (!res.ok) throw new Error(`Error al cargar configuración (${res.status})`);
  return (await res.json()) as AIChatConfig;
}

export async function updateAIChatConfig(patch: AIChatConfigPatch): Promise<AIChatConfig> {
  const res = await apiFetch(`${BASE}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Error al guardar (${res.status})`);
  }
  return (await res.json()) as AIChatConfig;
}

export async function fetchAIChatStatus(): Promise<AIChatStatus> {
  const res = await apiFetch(`${BASE}/status`);
  if (!res.ok) throw new Error(`Error al consultar estado (${res.status})`);
  return (await res.json()) as AIChatStatus;
}

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  const res = await apiFetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    let detail = text;
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      if (parsed.detail) detail = parsed.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Error en chat (${res.status})`);
  }
  return (await res.json()) as ChatResponse;
}

export async function resetConversation(userId: string, channelId?: string): Promise<{ deleted: number }> {
  const url = channelId
    ? `${BASE}/conversations/${encodeURIComponent(userId)}?channel_id=${encodeURIComponent(channelId)}`
    : `${BASE}/conversations/${encodeURIComponent(userId)}`;
  const res = await apiFetch(url, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Error al resetear (${res.status})`);
  return (await res.json()) as { deleted: number };
}

