import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import './RankingDrawer.css';
import type { RankingResponse, PhaseSummary } from '@/api/openrouter';

interface Props {
  open: boolean;
  phase: PhaseSummary | null;
  ranking: RankingResponse | null;
  loading?: boolean;
  onClose: () => void;
}

function rankClass(rank: number): string {
  if (rank === 1) return 'or-ranking-drawer__rank or-ranking-drawer__rank--gold';
  if (rank === 2) return 'or-ranking-drawer__rank or-ranking-drawer__rank--silver';
  if (rank === 3) return 'or-ranking-drawer__rank or-ranking-drawer__rank--bronze';
  return 'or-ranking-drawer__rank';
}

function formatPrice(v: number | null | undefined): string {
  if (v == null) return '—';
  if (v < 0) return 'var.';
  if (v === 0) return 'gratis';
  return `$${v.toFixed(v < 0.01 ? 4 : 2)}`;
}

export default function RankingDrawer({
  open,
  phase,
  ranking,
  loading,
  onClose,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open || !phase) return null;

  const entries = ranking?.entries ?? [];

  return createPortal(
    <div
      className="or-ranking-drawer-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="or-ranking-drawer" role="dialog" aria-modal="true">
        <div className="or-ranking-drawer__header">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-on-surface-variant font-bold mb-1">
              Top 10 modelos
            </p>
            <h2 className="font-display text-headline-lg text-primary leading-none">
              {phase.label}
            </h2>
            <p className="text-xs text-on-surface-variant mt-1">
              {phase.active_benchmarks_count} benchmarks activos ·{' '}
              {phase.reserved_benchmarks_count} reservados ·{' '}
              {phase.feature_factors_count} features
            </p>
          </div>
          <button
            type="button"
            className="or-ranking-drawer__close"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="or-ranking-drawer__body">
          {loading && (
            <p className="text-xs text-on-surface-variant text-center py-6">
              <span className="material-symbols-outlined animate-openrouter-spin align-middle mr-1 text-[14px]">
                progress_activity
              </span>
              Cargando ranking...
            </p>
          )}
          {!loading && entries.length === 0 && (
            <div className="text-center text-xs text-on-surface-variant py-8">
              <span className="material-symbols-outlined text-[36px] opacity-40 mb-2 block">
                query_stats
              </span>
              <p className="font-bold mb-1">Sin datos de ranking</p>
              <p className="opacity-70">
                Espera al próximo scrape de AA + BFCL para popular benchmarks.
              </p>
            </div>
          )}
          {!loading &&
            entries.map((entry, idx) => (
              <div
                key={entry.model_id}
                className="or-ranking-drawer__entry animate-openrouter-row-fade"
                style={{ animationDelay: `${idx * 50}ms` }}
              >
                <span className={rankClass(entry.rank)}>{entry.rank}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-on-surface truncate">
                    {entry.model_name || entry.model_id}
                  </p>
                  <p className="text-[11px] text-on-surface-variant truncate">
                    {entry.model_id}
                  </p>
                  <div className="or-ranking-drawer__score-bar">
                    <div
                      className="or-ranking-drawer__score-bar-fill"
                      style={{ width: `${Math.min(100, entry.score * 100)}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-on-surface-variant mt-1 flex justify-between">
                    <span>Score: {entry.score.toFixed(3)}</span>
                    <span>
                      {formatPrice(entry.pricing_prompt_per_mtok)} /{' '}
                      {formatPrice(entry.pricing_completion_per_mtok)} /Mtok
                    </span>
                  </p>
                </div>
              </div>
            ))}
        </div>

        <div className="or-ranking-drawer__footer">
          <span>Top {entries.length} de la fase {phase.slug}</span>
          <span>Esc o click afuera para cerrar</span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
