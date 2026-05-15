import './StatusCard.css';
import type { OpenRouterStatus } from '@/api/openrouter';

type RefreshState = 'idle' | 'loading' | 'success' | 'error';

interface Props {
  status: OpenRouterStatus | null;
  loading?: boolean;
  refreshState: RefreshState;
  onRefresh: () => void;
}

const WARNING_LABELS: Record<string, string> = {
  aa_api_key_missing: 'Clave API de AA faltante',
  bfcl_scrape_stale: 'Scrape BFCL desactualizado',
  aa_scrape_stale: 'Scrape AA desactualizado',
  bfcl_scrape_error: 'Error reciente en scrape BFCL',
  aa_scrape_error: 'Error reciente en scrape AA',
};

function formatTimeAgo(ts: number | null): string {
  if (ts == null) return 'Sin datos';
  const diff = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (diff < 60) return `Hace ${diff}s`;
  if (diff < 3600) return `Hace ${Math.floor(diff / 60)}min`;
  if (diff < 86400) return `Hace ${Math.floor(diff / 3600)}h`;
  return `Hace ${Math.floor(diff / 86400)}d`;
}

export default function StatusCard({ status, loading, refreshState, onRefresh }: Props) {
  const warnings = status?.warnings ?? [];
  const modelsCount = status?.models_count ?? 0;
  const lastFetched = status?.last_fetched_at ?? null;
  const refreshing = refreshState === 'loading';

  return (
    <div className="openrouter-status-card p-6 h-full">
      <div className="openrouter-status-card__pattern" />
      <div className="flex justify-between items-start mb-6 relative">
        <div>
          <h3 className="font-display text-headline-lg text-primary mb-1">
            Estado del Catálogo
          </h3>
          <p className="text-on-surface-variant opacity-70 text-sm">
            Monitoreo en tiempo real de modelos e infraestructura
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className={`openrouter-status-card__refresh-btn ${
            refreshState === 'success' ? 'animate-openrouter-bloom' : ''
          } ${refreshState === 'error' ? 'animate-openrouter-shake' : ''}`}
        >
          <span
            className={`material-symbols-outlined text-[18px] ${
              refreshing ? 'animate-openrouter-spin' : ''
            }`}
          >
            {refreshState === 'success' ? 'check' : 'sync'}
          </span>
          <span>
            {refreshing
              ? 'Actualizando...'
              : refreshState === 'success'
                ? '¡Actualizado!'
                : refreshState === 'error'
                  ? 'Error'
                  : 'Actualizar catálogo'}
          </span>
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4 relative">
        <div className="openrouter-status-card__stat p-4">
          <p className="text-[10px] text-on-surface-variant uppercase tracking-wider mb-1 font-bold">
            Caché Activo
          </p>
          <p className="text-2xl font-display text-secondary">
            {loading ? (
              <span className="openrouter-skeleton inline-block w-24 h-7 rounded" />
            ) : (
              <>{modelsCount.toLocaleString()} modelos</>
            )}
          </p>
        </div>
        <div className="openrouter-status-card__stat p-4">
          <p className="text-[10px] text-on-surface-variant uppercase tracking-wider mb-1 font-bold">
            Sincronización
          </p>
          <p className="text-2xl font-display text-primary">
            {loading ? (
              <span className="openrouter-skeleton inline-block w-20 h-7 rounded" />
            ) : (
              formatTimeAgo(lastFetched)
            )}
          </p>
        </div>
        <div
          className={`openrouter-status-card__stat p-4 flex items-center gap-3 ${
            warnings.length > 0 ? 'animate-openrouter-stale-warn' : ''
          }`}
        >
          <span
            className={`material-symbols-outlined ${
              warnings.length > 0 ? 'text-error' : 'text-tertiary'
            }`}
          >
            {warnings.length > 0 ? 'warning' : 'check_circle'}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant mb-0.5">
              {warnings.length > 0 ? 'Alertas' : 'Todo en orden'}
            </p>
            <p className="text-xs text-on-surface truncate">
              {warnings.length > 0
                ? WARNING_LABELS[warnings[0]] ?? warnings[0]
                : 'Sin alertas activas'}
            </p>
          </div>
        </div>
      </div>

      {warnings.length > 1 && (
        <div className="mt-3 flex flex-wrap gap-2 relative">
          {warnings.slice(1).map((w) => (
            <span
              key={w}
              className="openrouter-status-card__warning animate-openrouter-row-fade"
            >
              <span className="material-symbols-outlined text-[14px]">error</span>
              {WARNING_LABELS[w] ?? w}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
