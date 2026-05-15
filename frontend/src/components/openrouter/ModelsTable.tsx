import './ModelsTable.css';
import type { OpenRouterModel } from '@/api/openrouter';

interface Props {
  models: OpenRouterModel[];
  loading?: boolean;
  total?: number;
  onSelectModel?: (model: OpenRouterModel) => void;
  onShowAll?: () => void;
}

function getProvider(id: string): string {
  const idx = id.indexOf('/');
  if (idx < 0) return 'Otro';
  return id.slice(0, idx);
}

export function formatPrice(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value < 0) return 'Variable';
  if (value === 0) return 'Gratis';
  if (value < 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(2)}`;
}

export function formatContext(ctx: number | null | undefined): string {
  if (ctx == null) return '—';
  if (ctx >= 1_000_000) return `${(ctx / 1_000_000).toFixed(1)}M`;
  if (ctx >= 1_000) return `${Math.round(ctx / 1_000)}k`;
  return String(ctx);
}

export const PROVIDER_LABELS: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google',
  deepseek: 'DeepSeek',
  meta: 'Meta',
  'x-ai': 'xAI',
  xai: 'xAI',
  mistralai: 'Mistral',
  qwen: 'Qwen',
  cohere: 'Cohere',
  openrouter: 'OpenRouter',
};

export default function ModelsTable({
  models,
  loading,
  total,
  onSelectModel,
  onShowAll,
}: Props) {
  // Mostrar solo los 5 modelos mas baratos (rankeados por suma prompt+completion)
  const visible = [...models]
    .filter((m) => {
      const p = m.pricing_prompt_per_mtok;
      const c = m.pricing_completion_per_mtok;
      return p != null && c != null && p >= 0 && c >= 0;
    })
    .sort((a, b) => {
      const sa = (a.pricing_prompt_per_mtok ?? 0) + (a.pricing_completion_per_mtok ?? 0);
      const sb = (b.pricing_prompt_per_mtok ?? 0) + (b.pricing_completion_per_mtok ?? 0);
      return sa - sb;
    })
    .slice(0, 5);

  return (
    <div className="openrouter-models-card h-full">
      <div className="openrouter-models-card__header">
        <div>
          <h3 className="font-display text-headline-md text-primary">Catálogo de Modelos</h3>
          <p className="text-xs text-on-surface-variant mt-0.5">
            Top 5 modelos más baratos · {total ?? models.length} total
          </p>
        </div>
        <button
          type="button"
          onClick={onShowAll}
          className="openrouter-models-card__cta-btn"
        >
          <span className="material-symbols-outlined text-[16px]">grid_view</span>
          Ver todos los modelos
        </button>
      </div>

      <div className="openrouter-models-card__body">
        <table className="openrouter-models-card__table">
          <thead>
            <tr>
              <th>ID / Proveedor</th>
              <th>Nombre</th>
              <th className="text-right">Prompt $/M</th>
              <th className="text-right">Compl. $/M</th>
              <th>Contexto</th>
              <th>Modalidades</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="text-center py-8 text-on-surface-variant text-sm">
                  <span className="material-symbols-outlined animate-openrouter-spin align-middle mr-2">
                    progress_activity
                  </span>
                  Cargando modelos...
                </td>
              </tr>
            )}
            {!loading && visible.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-8 text-on-surface-variant text-sm">
                  Sin modelos en caché
                </td>
              </tr>
            )}
            {!loading &&
              visible.map((m, idx) => {
                const isFree =
                  m.pricing_prompt_per_mtok === 0 && m.pricing_completion_per_mtok === 0;
                const provLabel = PROVIDER_LABELS[getProvider(m.id)] ?? getProvider(m.id);
                const mods = m.modalities ?? [];
                return (
                  <tr
                    key={m.id}
                    className="animate-openrouter-row-fade cursor-pointer"
                    style={{ animationDelay: `${idx * 30}ms` }}
                    onClick={() => onSelectModel?.(m)}
                  >
                    <td>
                      <div className="flex flex-col">
                        <span className="font-medium text-sm truncate">{m.id}</span>
                        <span className="text-[10px] text-on-surface-variant">{provLabel}</span>
                      </div>
                    </td>
                    <td className="font-semibold text-secondary text-sm">
                      {m.name || m.id.split('/').pop()}
                    </td>
                    <td
                      className={`openrouter-models-card__price ${
                        isFree ? 'openrouter-models-card__price--free' : ''
                      }`}
                    >
                      {formatPrice(m.pricing_prompt_per_mtok)}
                    </td>
                    <td
                      className={`openrouter-models-card__price ${
                        isFree ? 'openrouter-models-card__price--free' : ''
                      }`}
                    >
                      {formatPrice(m.pricing_completion_per_mtok)}
                    </td>
                    <td className="text-sm">{formatContext(m.context_length)}</td>
                    <td>
                      <div className="flex gap-1">
                        {mods.length === 0 ? (
                          <span className="openrouter-models-card__badge">TEXT</span>
                        ) : (
                          mods.slice(0, 3).map((mod) => (
                            <span
                              key={mod}
                              className={`openrouter-models-card__badge ${
                                mod === 'image' || mod === 'vision'
                                  ? 'openrouter-models-card__badge--vision'
                                  : ''
                              }`}
                            >
                              {mod.toUpperCase()}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
