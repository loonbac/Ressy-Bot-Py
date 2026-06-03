import './StatusCard.css';
import type { AIChatConfig, MinimaxModel } from '@/api/ai-chat';

interface Props {
  config: AIChatConfig;
  models: MinimaxModel[];
  modelsLoading: boolean;
  onPatch: (patch: Partial<AIChatConfig>) => void;
}

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      className={`ai-chat-toggle ${on ? 'ai-chat-toggle--on' : ''}`}
    >
      <span className="ai-chat-toggle__thumb" />
    </button>
  );
}

export default function StatusCard({ config, models, modelsLoading, onPatch }: Props) {
  const knownModel = models.some((m) => m.id === config.chat_model);
  const budgetK = Math.round(config.context_token_budget / 1000);
  return (
    <div className="ai-chat-card animate-ai-chat-card-enter animate-ai-chat-stagger-2 w-full flex flex-col">
      <div className="flex items-center gap-3 mb-6">
        <span className="ai-chat-card__icon material-symbols-outlined">tune</span>
        <h3 className="font-headline-md text-headline-md text-primary">Modelo &amp; Contexto</h3>
      </div>

      <div className="space-y-5">
        <div>
          <label className="ai-chat-label">
            Modelo conversacional
            {modelsLoading && <span className="ml-2 opacity-60">cargando...</span>}
          </label>
          <div className="ai-chat-select-wrap">
            <select
              className="ai-chat-input ai-chat-select"
              value={config.chat_model}
              onChange={(e) => onPatch({ chat_model: e.target.value })}
              disabled={modelsLoading && models.length === 0}
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
              {!knownModel && config.chat_model && (
                <option value={config.chat_model}>{config.chat_model} · personalizado</option>
              )}
            </select>
            <span className="material-symbols-outlined ai-chat-select__chevron">expand_more</span>
          </div>
          <p className="ai-chat-hint">
            Catálogo completo de MiniMax. Usado por <code>/ia</code> y menciones al bot.
          </p>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="ai-chat-label">Ventana reciente</label>
            <span className="ai-chat-slider-value">{config.max_context_messages}</span>
          </div>
          <input
            type="range"
            min={10}
            max={200}
            value={config.max_context_messages}
            onChange={(e) => onPatch({ max_context_messages: Number(e.target.value) })}
            className="ai-chat-slider"
          />
          <p className="ai-chat-hint">
            Mensajes recientes que se conservan textualmente. Los más viejos se comprimen solos en la memoria
            (no se pierden).
          </p>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="ai-chat-label">Presupuesto de contexto</label>
            <span className="ai-chat-slider-value">{budgetK}k</span>
          </div>
          <input
            type="range"
            min={10}
            max={900}
            step={10}
            value={budgetK}
            onChange={(e) => onPatch({ context_token_budget: Number(e.target.value) * 1000 })}
            className="ai-chat-slider"
          />
          <p className="ai-chat-hint">
            Tokens máximos de historial reciente enviados al modelo. MiniMax-M3 admite hasta 1M de contexto.
          </p>
        </div>

        <div className="ai-chat-toggle-row justify-between w-full" onClick={() => onPatch({ memory_enabled: !config.memory_enabled })}>
          <div>
            <span className="ai-chat-label">Memoria de largo plazo</span>
            <p className="ai-chat-hint">Recuerda datos del usuario y del servidor entre conversaciones, automático.</p>
          </div>
          <Toggle on={config.memory_enabled} onToggle={() => onPatch({ memory_enabled: !config.memory_enabled })} />
        </div>

        <div className="ai-chat-toggle-row justify-between w-full" onClick={() => onPatch({ summary_enabled: !config.summary_enabled })}>
          <div>
            <span className="ai-chat-label">Resumen automático</span>
            <p className="ai-chat-hint">Comprime las conversaciones largas en un resumen persistente.</p>
          </div>
          <Toggle on={config.summary_enabled} onToggle={() => onPatch({ summary_enabled: !config.summary_enabled })} />
        </div>
      </div>
    </div>
  );
}
