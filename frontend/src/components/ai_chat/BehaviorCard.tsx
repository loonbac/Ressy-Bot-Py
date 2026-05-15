import './BehaviorCard.css';
import type { AIChatConfig } from '@/api/ai-chat';

interface Props {
  config: AIChatConfig;
  onPatch: (patch: Partial<AIChatConfig>) => void;
}

export default function BehaviorCard({ config, onPatch }: Props) {
  const promptCount = config.system_prompt.length;

  return (
    <div className="ai-chat-card ai-chat-behavior-card animate-ai-chat-card-enter animate-ai-chat-stagger-3 w-full flex flex-col">
      <div className="flex items-center gap-3 mb-6">
        <span className="ai-chat-card__icon material-symbols-outlined">psychology</span>
        <div>
          <h3 className="font-headline-md text-headline-md text-primary">Comportamiento del Asistente</h3>
          <p className="text-[11px] text-on-surface-variant">
            Define el tono, la cobertura y los límites del modelo.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
        <div className="md:col-span-2">
          <div className="flex justify-between items-center mb-2">
            <label className="ai-chat-label">Prompt del sistema</label>
            <span className="text-[11px] text-on-surface-variant font-mono">{promptCount} caracteres</span>
          </div>
          <textarea
            className="ai-chat-textarea"
            rows={5}
            value={config.system_prompt}
            placeholder="Eres una guía serena del santuario digital. Responde en español neutro peruano, con claridad y brevedad."
            onChange={(e) => onPatch({ system_prompt: e.target.value })}
          />
          <p className="ai-chat-hint">
            Se inyecta como mensaje <code>system</code> en cada llamada a MiniMax. Define el rol, idioma y restricciones.
          </p>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="ai-chat-label">Cooldown por usuario</label>
            <span className="ai-chat-slider-value">{config.rate_limit_seconds}s</span>
          </div>
          <input
            type="range"
            min={1}
            max={120}
            value={config.rate_limit_seconds}
            onChange={(e) => onPatch({ rate_limit_seconds: Number(e.target.value) })}
            className="ai-chat-slider"
          />
          <p className="ai-chat-hint">
            Segundos mínimos entre dos consultas del mismo usuario. Protege la cuota de la API y el rate limit de Discord.
          </p>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="ai-chat-label">Memoria activa</label>
            <span className="ai-chat-slider-value">{config.max_context_messages}</span>
          </div>
          <div className="ai-chat-memory-bar">
            <div
              className="ai-chat-memory-bar__fill"
              style={{ width: `${Math.min(100, (config.max_context_messages / 50) * 100)}%` }}
            />
          </div>
          <p className="ai-chat-hint">
            Visualización del contexto activo. Mensajes más antiguos se descartan al construir el prompt.
          </p>
        </div>
      </div>
    </div>
  );
}
