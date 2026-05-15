import './TopOrchestratorCard.css';
import type { RankingResponse } from '@/api/openrouter';

interface Props {
  ranking: RankingResponse | null;
  loading?: boolean;
  onViewMore?: () => void;
}

function rankClass(rank: number): string {
  if (rank === 1) return 'or-top-orchestrator-card__rank or-top-orchestrator-card__rank--gold';
  if (rank === 2) return 'or-top-orchestrator-card__rank or-top-orchestrator-card__rank--silver';
  if (rank === 3) return 'or-top-orchestrator-card__rank or-top-orchestrator-card__rank--bronze';
  return 'or-top-orchestrator-card__rank';
}

function formatPrice(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value < 0) return 'var.';
  if (value === 0) return 'gratis';
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`;
}

export default function TopOrchestratorCard({ ranking, loading, onViewMore }: Props) {
  const entries = ranking?.entries?.slice(0, 3) ?? [];

  return (
    <div className="or-top-orchestrator-card animate-openrouter-card-enter">
      <div className="or-top-orchestrator-card__pattern" />

      <div className="flex items-center justify-between relative">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-secondary text-[20px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            workspace_premium
          </span>
          <div>
            <h4 className="font-headline-md text-headline-md text-primary leading-tight">
              Top Orquestador
            </h4>
            <p className="text-[10px] text-on-surface-variant uppercase tracking-wider font-bold">
              Mejores modelos hoy
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onViewMore}
          className="text-[10px] font-bold uppercase tracking-wider text-secondary hover:underline transition-colors flex-shrink-0"
        >
          Ver +
        </button>
      </div>

      <div className="space-y-2 relative">
        {loading && (
          <p className="text-xs text-on-surface-variant text-center py-3">
            <span className="material-symbols-outlined animate-openrouter-spin align-middle mr-1 text-[14px]">
              progress_activity
            </span>
            Cargando ranking...
          </p>
        )}

        {!loading && entries.length === 0 && (
          <div className="or-top-orchestrator-card__empty">
            <span className="material-symbols-outlined text-[28px] opacity-50">
              query_stats
            </span>
            <p className="mt-1">Sin datos de ranking aún</p>
            <p className="text-[10px] opacity-60 mt-1">
              Espera al próximo scrape de AA + BFCL
            </p>
          </div>
        )}

        {!loading &&
          entries.map((entry, idx) => (
            <div
              key={entry.model_id}
              className="or-top-orchestrator-card__row animate-openrouter-row-fade"
              style={{ animationDelay: `${idx * 80}ms` }}
            >
              <span className={rankClass(entry.rank)}>{entry.rank}</span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold text-on-surface truncate">
                  {entry.model_name || entry.model_id}
                </p>
                <p className="text-[10px] text-on-surface-variant truncate">
                  Score {entry.score.toFixed(3)} ·{' '}
                  {formatPrice(entry.pricing_prompt_per_mtok)}/
                  {formatPrice(entry.pricing_completion_per_mtok)}
                </p>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}
