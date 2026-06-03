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
          <div
            className="ai-chat-toggle-row justify-between w-full mb-2"
            onClick={() => onPatch({ tools_enabled: !config.tools_enabled })}
          >
            <label className="ai-chat-label">Tools de lectura del servidor</label>
            <button
              type="button"
              role="switch"
              aria-checked={config.tools_enabled}
              onClick={(e) => {
                e.stopPropagation();
                onPatch({ tools_enabled: !config.tools_enabled });
              }}
              className={`ai-chat-toggle ${config.tools_enabled ? 'ai-chat-toggle--on' : ''}`}
            >
              <span className="ai-chat-toggle__thumb" />
            </button>
          </div>
          {config.tools_enabled && (
            <div className="mb-2">
              <div className="flex justify-between items-center mb-2">
                <span className="ai-chat-label">Mensajes escaneados por canal</span>
                <span className="ai-chat-slider-value">{config.tools_search_scan_limit}</span>
              </div>
              <input
                type="range"
                min={50}
                max={2000}
                step={50}
                value={config.tools_search_scan_limit}
                onChange={(e) => onPatch({ tools_search_scan_limit: Number(e.target.value) })}
                className="ai-chat-slider"
              />
            </div>
          )}
          <p className="ai-chat-hint">
            Permite a la IA buscar mensajes, miembros y canales del servidor seleccionado. Solo lectura, acotado a
            ese servidor.
          </p>
        </div>
      </div>
    </div>
  );
}
