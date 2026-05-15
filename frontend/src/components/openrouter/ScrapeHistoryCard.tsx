import './ScrapeHistoryCard.css';
import type { ScrapeRun } from '@/api/openrouter';

interface Props {
  runs: ScrapeRun[];
  loading?: boolean;
}

const SOURCE_LABELS: Record<string, string> = {
  artificial_analysis: 'Artificial Analysis',
  bfcl: 'BFCL',
  bfcl_github: 'BFCL',
  openrouter: 'OpenRouter',
};

function statusIcon(status: string): { kind: 'ok' | 'error' | 'warn'; icon: string } {
  if (status === 'ok') return { kind: 'ok', icon: 'check_circle' };
  if (status === 'error') return { kind: 'error', icon: 'error' };
  return { kind: 'warn', icon: 'warning' };
}

function formatClock(ts: number | null | undefined): string {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });
}

export default function ScrapeHistoryCard({ runs, loading }: Props) {
  return (
    <div className="openrouter-history-card h-full overflow-hidden">
      <div className="flex items-center gap-3 mb-3">
        <span className="material-symbols-outlined text-primary text-[20px]">history</span>
        <h3 className="font-display text-headline-md text-primary">Historial de Scrapes</h3>
      </div>
      <div className="space-y-1 overflow-y-auto min-h-0 flex-1">
        {loading && (
          <p className="text-xs text-on-surface-variant text-center py-3">
            <span className="material-symbols-outlined animate-openrouter-spin align-middle mr-1 text-[14px]">
              progress_activity
            </span>
            Cargando historial...
          </p>
        )}
        {!loading && runs.length === 0 && (
          <p className="text-xs text-on-surface-variant text-center py-3">
            Sin scrapes registrados todavía.
          </p>
        )}
        {!loading &&
          runs.slice(0, 12).map((run, idx) => {
            const { kind, icon } = statusIcon(run.status);
            const sourceLabel = SOURCE_LABELS[run.source] ?? run.source;
            const finishedTxt = formatClock(run.finished_at);
            return (
              <div
                key={`${run.source}-${run.started_at}`}
                className="openrouter-history-card__row animate-openrouter-row-fade"
                style={{ animationDelay: `${idx * 30}ms` }}
              >
                <span className="openrouter-history-card__time">{finishedTxt}</span>
                <div className="flex-grow min-w-0">
                  <p className="text-sm font-medium truncate">
                    {sourceLabel}: {run.status === 'ok' ? `${run.rows_updated} modelos actualizados` : 'falló'}
                  </p>
                  <p className="text-[10px] text-on-surface-variant truncate">
                    {run.error ?? `Aliases descartados: ${run.aliases_missed ?? 0}`}
                  </p>
                </div>
                <span
                  className={`material-symbols-outlined text-[18px] openrouter-history-card__icon--${kind}`}
                >
                  {icon}
                </span>
              </div>
            );
          })}
      </div>
    </div>
  );
}
