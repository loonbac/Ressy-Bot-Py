import './StatusCard.css';
import type { AIChatConfig, MinimaxModel } from '@/api/ai-chat';

interface Props {
  config: AIChatConfig;
  models: MinimaxModel[];
  modelsLoading: boolean;
  onPatch: (patch: Partial<AIChatConfig>) => void;
}

export default function StatusCard({ config, models, modelsLoading, onPatch }: Props) {
  const knownModel = models.some((m) => m.id === config.chat_model);
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
            Catálogo completo de MiniMax. Usado por <code>/preguntar</code>, <code>/charlar</code> y menciones.
          </p>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="ai-chat-label">Mensajes de contexto</label>
            <span className="ai-chat-slider-value">{config.max_context_messages}</span>
          </div>
          <input
            type="range"
            min={1}
            max={50}
            value={config.max_context_messages}
            onChange={(e) => onPatch({ max_context_messages: Number(e.target.value) })}
            className="ai-chat-slider"
          />
          <p className="ai-chat-hint">Cantidad máxima de turnos previos enviados al modelo por conversación.</p>
        </div>
      </div>
    </div>
  );
}
