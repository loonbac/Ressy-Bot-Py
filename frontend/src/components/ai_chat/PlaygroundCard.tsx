import { useEffect, useRef, useState } from 'react';
import './PlaygroundCard.css';
import { sendChatMessage, resetConversation, type AIChatConfig } from '@/api/ai-chat';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  thinking?: string | null;
  ts: number;
}

interface Props {
  config: AIChatConfig;
  showToast: (kind: 'success' | 'error', text: string) => void;
}

const SANDBOX_USER_ID = 'dashboard-playground';
const SANDBOX_CHANNEL_ID = 'dashboard';

export default function PlaygroundCard({ config, showToast }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [resetting, setResetting] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  const submit = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: text, ts: Date.now() }]);
    setSending(true);
    try {
      const res = await sendChatMessage({
        user_id: SANDBOX_USER_ID,
        channel_id: SANDBOX_CHANNEL_ID,
        message: text,
      });
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.reply, thinking: res.thinking, ts: Date.now() },
      ]);
    } catch (err) {
      const detail = err instanceof Error ? err.message : 'Error desconocido';
      setMessages((prev) => [
        ...prev,
        { role: 'system', content: `⚠ ${detail}`, ts: Date.now() },
      ]);
      showToast('error', detail);
    } finally {
      setSending(false);
    }
  };

  const reset = async () => {
    setResetting(true);
    try {
      await resetConversation(SANDBOX_USER_ID, SANDBOX_CHANNEL_ID);
      setMessages([]);
      showToast('success', 'Contexto del playground reiniciado');
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error al resetear');
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="ai-chat-card ai-chat-playground-card animate-ai-chat-card-enter animate-ai-chat-stagger-4">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <span className="ai-chat-card__icon material-symbols-outlined">forum</span>
          <div>
            <h3 className="font-headline-md text-headline-md text-primary">Laboratorio de Pruebas</h3>
            <p className="text-[11px] text-on-surface-variant">
              Conversa con el modelo activo desde el panel. El contexto se guarda como usuario sandbox.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={reset}
          disabled={resetting || messages.length === 0}
          className="ai-chat-secondary-btn"
        >
          <span className={`material-symbols-outlined text-[16px] ${resetting ? 'animate-ai-chat-spin' : ''}`}>
            restart_alt
          </span>
          {resetting ? 'Limpiando...' : 'Limpiar'}
        </button>
      </div>

      <div ref={scrollRef} className="ai-chat-playground__feed">
        {messages.length === 0 && !sending && (
          <div className="ai-chat-playground__empty">
            <span className="material-symbols-outlined text-[32px]">chat_bubble</span>
            <p className="text-[13px]">Envía una pregunta para conversar con <strong>{config.chat_model}</strong>.</p>
          </div>
        )}
        {messages.map((m, idx) => (
          <div
            key={`${m.ts}-${idx}`}
            className={`ai-chat-playground__msg ai-chat-playground__msg--${m.role} animate-ai-chat-msg-in`}
          >
            <div className="ai-chat-playground__bubble-wrap">
              {m.thinking ? (
                <details className="ai-chat-playground__thinking">
                  <summary>
                    <span className="material-symbols-outlined text-[14px]">psychology</span>
                    Razonamiento del modelo
                    <span className="ai-chat-playground__thinking-meta">
                      {m.thinking.length} caracteres
                    </span>
                  </summary>
                  <pre className="ai-chat-playground__thinking-body">{m.thinking}</pre>
                </details>
              ) : null}
              <div className="ai-chat-playground__bubble">{m.content}</div>
            </div>
          </div>
        ))}
        {sending && (
          <div className="ai-chat-playground__msg ai-chat-playground__msg--assistant animate-ai-chat-msg-in">
            <div className="ai-chat-playground__bubble ai-chat-typing">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
      </div>

      <div className="ai-chat-playground__inputrow">
        <input
          type="text"
          className="ai-chat-input ai-chat-playground__input"
          placeholder={config.enabled ? 'Escribe un mensaje de prueba...' : 'Plugin desactivado — actívalo arriba para chatear.'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
          disabled={!config.enabled || sending}
        />
        <button
          type="button"
          className="ai-chat-send-btn"
          onClick={() => void submit()}
          disabled={!config.enabled || sending || input.trim().length === 0}
          aria-label="Enviar mensaje"
        >
          <span className={`material-symbols-outlined text-[20px] ${sending ? 'animate-ai-chat-spin' : ''}`}>
            {sending ? 'progress_activity' : 'send'}
          </span>
        </button>
      </div>
    </div>
  );
}
