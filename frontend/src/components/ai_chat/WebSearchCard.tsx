import './WebSearchCard.css';
import type { AIChatConfig } from '@/api/ai-chat';

interface Props {
  config: AIChatConfig;
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

export default function WebSearchCard({ config, onPatch }: Props) {
  const safeToggle = config.search_enabled && config.search_safe;
  return (
    <div className="ai-chat-card ai-chat-web-search-card animate-ai-chat-card-enter animate-ai-chat-stagger-4 w-full flex flex-col">
      <div className="flex items-center gap-3 mb-6">
        <span className="ai-chat-card__icon material-symbols-outlined">travel_explore</span>
        <div>
          <h3 className="font-headline-md text-headline-md text-primary">Búsqueda Web</h3>
          <p className="text-[11px] text-on-surface-variant">
            Permite a la IA buscar en la web antes de responder.
          </p>
        </div>
      </div>

      <div className="space-y-5">
        <div className="ai-chat-toggle-row justify-between w-full" onClick={() => onPatch({ search_enabled: !config.search_enabled })}>
          <div>
            <span className="ai-chat-label">Activar búsqueda web</span>
            <p className="ai-chat-hint">
              Cuando está activo, la IA consulta DuckDuckGo Lite antes de responder preguntas de actualidad o
              información externa. Sin claves de API: la cuota se respeta por usuario.
            </p>
          </div>
          <Toggle on={config.search_enabled} onToggle={() => onPatch({ search_enabled: !config.search_enabled })} />
        </div>

        <div
          className={`ai-chat-toggle-row justify-between w-full ${!config.search_enabled ? 'ai-chat-web-search-card--disabled' : ''}`}
          onClick={() => config.search_enabled && onPatch({ search_safe: !config.search_safe })}
        >
          <div>
            <span className="ai-chat-label">Búsqueda segura (SafeSearch)</span>
            <p className="ai-chat-hint">
              Filtra contenido adulto en los resultados. Recomendado mantenerlo activo en servidores educativos.
            </p>
          </div>
          <Toggle
            on={safeToggle}
            onToggle={() => config.search_enabled && onPatch({ search_safe: !config.search_safe })}
          />
        </div>

        <div className={!config.search_enabled ? 'ai-chat-web-search-card--disabled' : ''}>
          <div className="flex justify-between items-center mb-2">
            <label className="ai-chat-label">Consultas por hora (por usuario)</label>
            <span className="ai-chat-slider-value">{config.search_max_per_hour}</span>
          </div>
          <input
            type="range"
            min={1}
            max={100}
            value={config.search_max_per_hour}
            onChange={(e) => onPatch({ search_max_per_hour: Number(e.target.value) })}
            className="ai-chat-slider"
            disabled={!config.search_enabled}
          />
          <p className="ai-chat-hint">
            Tope rolling-hour por usuario. Entre <code>1</code> y <code>100</code>. El backend rechaza cualquier
            valor fuera de ese rango al guardar.
          </p>
        </div>

        <p className="ai-chat-hint ai-chat-web-search-card__footnote">
          <span className="material-symbols-outlined ai-chat-web-search-card__footnote-icon">info</span>
          Cuando la búsqueda está desactivada, la IA sigue pudiendo leer páginas web que le pases en una URL con la
          herramienta <code>fetch_webpage</code>. Esta tarjeta solo controla el modo de búsqueda automática.
        </p>
      </div>
    </div>
  );
}
