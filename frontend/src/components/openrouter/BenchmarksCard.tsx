import './BenchmarksCard.css';
import type { BenchmarkRow } from '@/api/openrouter';

interface Props {
  benchmarks: BenchmarkRow[];
  loading?: boolean;
  onManage?: () => void;
}

const SLUG_LABELS: Record<string, string> = {
  ifbench: 'IFBench',
  multichallenge: 'MultiChallenge',
  tau2_telecom: 'τ²-Telecom',
  bfcl_v3: 'BFCL v3',
  bfcl_parallel: 'BFCL Parallel',
  aa_intelligence_index: 'AA Intelligence',
  ruler: 'RULER',
  longbench: 'LongBench',
  input_cache_read_ratio: 'Cache Read Ratio',
  supports_reasoning_effort: 'Reasoning Effort',
  supports_verbosity: 'Verbosity',
};

const SLUG_DESCRIPTIONS: Record<string, string> = {
  ifbench: 'Adherencia a instrucciones bajo restricciones',
  multichallenge: 'Coherencia en conversaciones multi-turno',
  tau2_telecom: 'Tool use con state en escenarios complejos',
  bfcl_v3: 'Function calling determinístico single-step',
  bfcl_parallel: 'Function calls paralelizables',
  aa_intelligence_index: 'Score compuesto de inteligencia agregada',
  ruler: 'Retención real en contextos largos',
  longbench: 'Tareas long-context multi-archivo',
  input_cache_read_ratio: 'Costo de cache read vs input normal',
  supports_reasoning_effort: 'Permite ajustar profundidad de reasoning',
  supports_verbosity: 'Permite ajustar verbosity del output',
};

const SOURCE_LABELS: Record<string, string> = {
  artificial_analysis: 'AA',
  bfcl_github: 'BFCL',
  bfcl: 'BFCL',
  manual: 'Manual',
  feature: 'Feature',
  openrouter: 'OpenRouter',
};

function sourceColor(source: string): string {
  if (source.startsWith('artificial')) return 'bg-primary-fixed text-on-primary-fixed';
  if (source.startsWith('bfcl')) return 'bg-secondary-fixed text-on-secondary-fixed';
  if (source === 'feature' || source === 'openrouter') return 'bg-tertiary-container text-on-tertiary-container';
  return 'bg-outline-variant/40 text-on-surface-variant';
}

export default function BenchmarksCard({ benchmarks, loading, onManage }: Props) {
  const sorted = [...benchmarks].sort((a, b) => {
    const ra = a.reserved === true ? 1 : 0;
    const rb = b.reserved === true ? 1 : 0;
    if (ra !== rb) return ra - rb;
    return (a.slug ?? '').localeCompare(b.slug ?? '');
  });

  const activeCount = benchmarks.filter((b) => !b.reserved).length;
  const reservedCount = benchmarks.filter((b) => b.reserved === true).length;
  const featureCount = benchmarks.filter((b) => b.is_feature_factor === true).length;

  return (
    <div className="openrouter-benchmarks-card h-full">
      <div className="openrouter-benchmarks-card__pattern" />
      <div className="flex items-center gap-3">
        <span className="material-symbols-outlined text-primary text-[22px]">
          analytics
        </span>
        <div className="flex-1">
          <h3 className="font-display text-headline-md text-primary">
            Catálogo de Benchmarks
          </h3>
          <p className="text-[11px] text-on-surface-variant">
            {activeCount} activos · {reservedCount} reservados · {featureCount} feature factors
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 flex-1 min-h-0 overflow-y-auto pr-1">
        {loading && (
          <div className="col-span-2 text-center text-xs text-on-surface-variant py-4">
            <span className="material-symbols-outlined animate-openrouter-spin align-middle mr-1 text-[14px]">
              progress_activity
            </span>
            Cargando benchmarks...
          </div>
        )}
        {!loading && sorted.length === 0 && (
          <p className="col-span-2 text-xs text-on-surface-variant text-center py-3">
            Sin benchmarks seedeados.
          </p>
        )}
        {!loading &&
          sorted.map((b, idx) => {
            const reserved = b.reserved === true;
            const isFeature = b.is_feature_factor === true;
            const label = SLUG_LABELS[b.slug] ?? b.slug;
            const desc = SLUG_DESCRIPTIONS[b.slug] ?? b.description ?? '';
            const sourceKey = b.source ?? 'manual';
            const sourceLabel = SOURCE_LABELS[sourceKey] ?? sourceKey;
            const usedBy = b.used_by_phases ?? 0;
            return (
              <div
                key={b.slug}
                className={`openrouter-benchmarks-card__cell animate-openrouter-row-fade ${
                  reserved ? 'openrouter-benchmarks-card__cell--reserved' : ''
                }`}
                style={{ animationDelay: `${idx * 35}ms` }}
                title={desc}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-bold text-on-surface truncate" title={label}>
                    {label}
                  </p>
                  <span
                    className={`text-[8px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ${sourceColor(sourceKey)}`}
                  >
                    {sourceLabel}
                  </span>
                </div>
                <p className="text-[10px] text-on-surface-variant line-clamp-2">
                  {desc || '—'}
                </p>
                <div className="flex items-center justify-between text-[9px] text-on-surface-variant mt-auto pt-1">
                  <span className="flex items-center gap-1">
                    {reserved ? (
                      <>
                        <span className="material-symbols-outlined text-[10px] text-error">
                          block
                        </span>
                        <span className="text-error font-bold uppercase">Reservado</span>
                      </>
                    ) : (
                      <>
                        <span className="material-symbols-outlined text-[10px] text-green-600">
                          check_circle
                        </span>
                        <span>Activo</span>
                      </>
                    )}
                  </span>
                  {isFeature && (
                    <span className="px-1.5 py-0.5 rounded bg-primary-container/40 text-primary font-bold text-[8px]">
                      FEATURE
                    </span>
                  )}
                  {usedBy > 0 && (
                    <span className="font-bold">
                      Usado por {usedBy} fase{usedBy === 1 ? '' : 's'}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
      </div>

      <button type="button" className="openrouter-benchmarks-card__btn" onClick={onManage}>
        Gestionar pesos por fase
      </button>
    </div>
  );
}
