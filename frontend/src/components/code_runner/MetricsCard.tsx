import './MetricsCard.css';
import type { CodeRunnerStats } from '@/api/code-runner';

interface Props {
  stats: CodeRunnerStats | null;
}

export default function MetricsCard({ stats }: Props) {
  const sessionsTotal = stats?.totals?.sessions_total ?? 0;
  const executionsTotal = stats?.totals?.executions_total ?? 0;
  const infractionsTotal = stats?.totals?.infractions_total ?? 0;
  const usersWithInfractions = stats?.totals?.users_with_infractions ?? 0;
  const blocked = stats?.executions_by_status?.blocked ?? 0;
  const langs = stats?.languages ?? [];
  const topLang = langs[0];
  const topLangPct = topLang && executionsTotal > 0
    ? Math.round((topLang.total / executionsTotal) * 100)
    : 0;

  return (
    <div className="cr-card cr-metrics-card animate-cr-card-enter animate-cr-stagger-2 w-full flex flex-col">
      <div className="flex items-center gap-3 mb-5">
        <span className="cr-card__icon material-symbols-outlined">monitoring</span>
        <h3 className="font-headline-md text-headline-md text-primary">Métricas</h3>
      </div>

      <div className="space-y-5">
        <div className="cr-metrics-card__row group">
          <span className="text-on-surface-variant text-sm">Total Sesiones</span>
          <span className="cr-metrics-card__num">{sessionsTotal.toLocaleString('es-PE')}</span>
        </div>
        <div className="cr-metrics-card__row group">
          <span className="text-on-surface-variant text-sm">Ejecuciones</span>
          <span className="cr-metrics-card__num">{executionsTotal.toLocaleString('es-PE')}</span>
        </div>

        <div className="pt-4 border-t border-outline-variant/30 space-y-4">
          {topLang ? (
            <div>
              <div className="flex justify-between items-center">
                <span className="cr-label !mb-0">Lenguaje más usado</span>
                <span className="text-secondary font-bold text-sm">{topLangPct}%</span>
              </div>
              <div className="flex justify-between items-center mt-1">
                <span className="font-medium text-sm">{topLang.language}</span>
                <span className="text-[11px] text-on-surface-variant">{topLang.total} ejec.</span>
              </div>
              <div className="cr-metrics-card__bar">
                <div
                  className="cr-metrics-card__bar-fill animate-cr-bar-grow"
                  style={{ width: `${topLangPct}%` }}
                />
              </div>
            </div>
          ) : (
            <div className="text-tertiary text-xs italic">Sin ejecuciones registradas todavía.</div>
          )}

          <div>
            <span className="cr-label">Bloqueos de seguridad</span>
            <span className="text-on-surface font-bold">{blocked} acumulados</span>
          </div>
          <div>
            <span className="cr-label">Infracciones</span>
            <span className="text-error font-bold">
              {infractionsTotal} ({usersWithInfractions} usuarios)
            </span>
          </div>
        </div>

        {langs.length > 1 && (
          <div className="pt-3 border-t border-outline-variant/30">
            <span className="cr-label">Top 5 lenguajes</span>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {langs.map((l, idx) => (
                <span
                  key={l.language}
                  className="cr-chip animate-cr-chip-pop"
                  style={{ animationDelay: `${idx * 60}ms` }}
                >
                  {l.language} · {l.total}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
