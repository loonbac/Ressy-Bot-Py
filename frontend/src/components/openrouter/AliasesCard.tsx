import { useState } from 'react';
import './AliasesCard.css';
import type { AliasEntry } from '@/api/openrouter';

interface Props {
  aliases: AliasEntry[];
  loading?: boolean;
  onCreateAlias?: () => void;
}

function scoreLevel(score: number | undefined): 'good' | 'warn' | 'bad' {
  if (score == null) return 'warn';
  if (score >= 0.9) return 'good';
  if (score >= 0.75) return 'warn';
  return 'bad';
}

export default function AliasesCard({ aliases, loading, onCreateAlias }: Props) {
  const [threshold, setThreshold] = useState(0.85);

  const visible = aliases.slice(0, 8);

  return (
    <div className="openrouter-aliases-card h-full">
      <div className="flex items-center justify-between">
        <h4 className="font-display text-headline-md text-primary">Alias Mapping</h4>
        <button
          type="button"
          onClick={onCreateAlias}
          className="text-[10px] font-bold uppercase tracking-wider text-secondary hover:text-secondary-container transition-colors"
        >
          + Crear
        </button>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-[10px] text-on-surface-variant font-bold uppercase">
          Umbral de Match
        </span>
        <span className="text-xs font-bold text-secondary">{threshold.toFixed(2)}</span>
      </div>
      <input
        type="range"
        min={0.5}
        max={1}
        step={0.01}
        value={threshold}
        onChange={(e) => setThreshold(Number(e.target.value))}
        className="openrouter-aliases-card__threshold"
      />

      <div className="space-y-2 overflow-y-auto min-h-0 flex-1">
        {loading && (
          <p className="text-xs text-on-surface-variant text-center py-3">
            <span className="material-symbols-outlined animate-openrouter-spin align-middle mr-1 text-[14px]">
              progress_activity
            </span>
            Cargando aliases...
          </p>
        )}
        {!loading && visible.length === 0 && (
          <p className="text-xs text-on-surface-variant text-center py-3">
            Sin aliases registrados todavía.
          </p>
        )}
        {!loading &&
          visible.map((alias, idx) => {
            const lvl = scoreLevel(alias.score);
            const isWarn = lvl === 'bad' || (alias.score ?? 1) < threshold;
            return (
              <div
                key={`${alias.openrouter_id}-${alias.source}`}
                className={`openrouter-aliases-card__row animate-openrouter-row-fade ${
                  isWarn ? 'openrouter-aliases-card__row--warn' : ''
                }`}
                style={{ animationDelay: `${idx * 35}ms` }}
              >
                <div className="truncate mr-2 min-w-0">
                  <p className="text-[11px] font-bold text-on-surface truncate">
                    {alias.openrouter_id}
                  </p>
                  <p className="text-[9px] text-on-surface-variant truncate">
                    {alias.source} · {alias.external_name}
                  </p>
                </div>
                {isWarn ? (
                  <span className="openrouter-aliases-card__warn-badge">Revisar</span>
                ) : (
                  <span
                    className={`openrouter-aliases-card__score openrouter-aliases-card__score--${lvl}`}
                  >
                    {(alias.score ?? 1).toFixed(2)}
                  </span>
                )}
              </div>
            );
          })}
      </div>
    </div>
  );
}
