import './PhasesGrid.css';
import type { PhaseSummary, RankingResponse } from '@/api/openrouter';

interface Props {
  phases: PhaseSummary[];
  rankings: Record<string, RankingResponse | null>;
  enabledPhases: string[];
  perPhaseEmbed: boolean;
  onTogglePhase: (slug: string, enabled: boolean) => void;
  onTogglePerPhaseEmbed: () => void;
  onShowRanking: (slug: string) => void;
  onEditWeights: (slug: string) => void;
  onSendEmbed?: (slug: string) => void;
}

export default function PhasesGrid({
  phases,
  rankings,
  enabledPhases,
  perPhaseEmbed,
  onTogglePhase,
  onTogglePerPhaseEmbed,
  onShowRanking,
  onEditWeights,
  onSendEmbed,
}: Props) {
  const enabledSet = new Set(enabledPhases);

  return (
    <section className="mt-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-headline-md text-primary">Fases SDD Modelos</h3>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onTogglePerPhaseEmbed}
            className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
              perPhaseEmbed
                ? 'bg-secondary-fixed text-on-secondary-fixed'
                : 'bg-surface-container text-on-surface-variant'
            }`}
          >
            Embed por fase: {perPhaseEmbed ? 'ON' : 'OFF'}
          </button>
          <span className="px-3 py-1 bg-surface-container text-on-surface-variant text-xs rounded-full font-medium">
            {enabledPhases.length} / {phases.length} activas
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {phases.map((phase, index) => {
          const isActive = enabledSet.has(phase.slug);
          const ranking = rankings[phase.slug] ?? null;
          const top1 = ranking?.entries?.[0];
          return (
            <div
              key={phase.slug}
              className={`openrouter-phase-card animate-openrouter-phase-enter ${
                isActive ? 'openrouter-phase-card--active' : 'openrouter-phase-card--disabled'
              }`}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className="flex justify-between items-start gap-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  {phase.slug === 'orchestrator' && (
                    <span
                      className="openrouter-phase-card__crown"
                      title="Fase principal"
                    >
                      <span className="material-symbols-outlined">workspace_premium</span>
                    </span>
                  )}
                  <h4 className="font-bold text-on-surface text-sm leading-tight truncate">
                    {phase.label}
                  </h4>
                </div>
                <button
                  type="button"
                  onClick={() => onTogglePhase(phase.slug, !isActive)}
                  className={`openrouter-phase-card__toggle ${
                    isActive ? 'openrouter-phase-card__toggle--on' : ''
                  }`}
                  aria-label={`Activar/desactivar ${phase.label}`}
                />
              </div>

              <div className="openrouter-phase-card__top1">
                <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-0.5">
                  Top 1
                </p>
                <p className="text-xs font-medium text-secondary truncate">
                  {top1 ? top1.model_name || top1.model_id : 'Sin datos'}
                </p>
              </div>

              <div className="flex justify-between text-[10px] text-on-surface-variant">
                <span>{phase.active_benchmarks_count} activos</span>
                <span>{phase.reserved_benchmarks_count} reservados</span>
              </div>

              <div className="flex gap-1.5">
                <button
                  type="button"
                  onClick={() => onShowRanking(phase.slug)}
                  className="openrouter-phase-card__btn openrouter-phase-card__btn--secondary"
                >
                  Ver
                </button>
                <button
                  type="button"
                  onClick={() => onEditWeights(phase.slug)}
                  className="openrouter-phase-card__btn openrouter-phase-card__btn--primary"
                >
                  Pesos
                </button>
              </div>
              {onSendEmbed && (
                <button
                  type="button"
                  onClick={() => onSendEmbed(phase.slug)}
                  className="openrouter-phase-card__send-btn"
                  title={`Enviar embed de ${phase.label} a Discord ahora`}
                >
                  <span className="material-symbols-outlined text-[12px]">send</span>
                  Enviar a Discord
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
