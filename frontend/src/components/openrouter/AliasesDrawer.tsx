import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import './AliasesDrawer.css';
import type { AliasEntry } from '@/api/openrouter';

interface Props {
  open: boolean;
  aliases: AliasEntry[];
  aliasesMissed?: number;
  loading?: boolean;
  onClose: () => void;
  onCreateAlias?: () => void;
}

function scoreLevel(score: number | undefined, threshold: number): 'good' | 'warn' | 'bad' {
  if (score == null) return 'warn';
  if (score >= 0.9) return 'good';
  if (score >= threshold) return 'warn';
  return 'bad';
}

export default function AliasesDrawer({
  open,
  aliases,
  aliasesMissed = 0,
  loading,
  onClose,
  onCreateAlias,
}: Props) {
  const [threshold, setThreshold] = useState(0.85);
  const [showOnlyWarn, setShowOnlyWarn] = useState(false);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  const filtered = useMemo(() => {
    if (!showOnlyWarn) return aliases;
    return aliases.filter((a) => scoreLevel(a.score, threshold) !== 'good');
  }, [aliases, showOnlyWarn, threshold]);

  const goodCount = aliases.filter((a) => (a.score ?? 1) >= 0.9).length;
  const warnCount = aliases.filter(
    (a) => (a.score ?? 1) >= threshold && (a.score ?? 1) < 0.9,
  ).length;

  if (!open) return null;

  return createPortal(
    <div
      className="or-aliases-drawer-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="or-aliases-drawer" role="dialog" aria-modal="true">
        <div className="or-aliases-drawer__header">
          <div>
            <h2 className="font-display text-headline-lg text-primary mb-0.5 leading-none">
              Conexión de nombres
            </h2>
            <p className="text-xs text-on-surface-variant">
              Por qué el ranking conoce a qué modelo aplicar cada benchmark
            </p>
          </div>
          <button
            type="button"
            className="or-aliases-drawer__close"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="or-aliases-drawer__explainer animate-openrouter-card-enter">
          <p>
            <strong>OpenRouter</strong> llama a los modelos con un ID
            (ej. <code>anthropic/claude-opus-4.7</code>). <strong>Artificial Analysis</strong> y{' '}
            <strong>BFCL</strong> los llaman distinto (ej. <code>Claude Opus 4.7</code>).
          </p>
          <p className="mt-2">
            El bot conecta automáticamente los nombres parecidos usando{' '}
            <strong>fuzzy matching</strong>. Sin esa conexión, los benchmarks de AA y BFCL
            no se asignan a ningún modelo y el ranking queda vacío.
          </p>
          <p className="mt-2 text-on-surface-variant">
            Esta pantalla solo es útil cuando aparecen <strong>matches sospechosos</strong> o
            modelos huérfanos. El 95% del tiempo no necesitas tocar nada.
          </p>
        </div>

        <div className="or-aliases-drawer__metric">
          <div className="or-aliases-drawer__metric-cell">
            <p className="or-aliases-drawer__metric-num">{goodCount}</p>
            <p className="or-aliases-drawer__metric-label">Confiables</p>
          </div>
          <div className="or-aliases-drawer__metric-cell">
            <p className="or-aliases-drawer__metric-num">{warnCount}</p>
            <p className="or-aliases-drawer__metric-label">Para revisar</p>
          </div>
          <div className="or-aliases-drawer__metric-cell">
            <p className="or-aliases-drawer__metric-num">{aliasesMissed}</p>
            <p className="or-aliases-drawer__metric-label">Sin match</p>
          </div>
        </div>

        <div className="or-aliases-drawer__threshold-row">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-on-surface-variant font-bold uppercase tracking-wider">
              Umbral de match
            </span>
            <span className="text-xs font-bold text-secondary">
              {threshold.toFixed(2)}
            </span>
          </div>
          <input
            type="range"
            min={0.5}
            max={0.99}
            step={0.01}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="or-aliases-drawer__threshold-slider"
          />
          <p className="text-[10px] text-on-surface-variant opacity-70">
            Más alto = menos matches pero más confiables. Más bajo = más cobertura, riesgo de
            falsos positivos.
          </p>
          <button
            type="button"
            className="or-aliases-drawer__rebuild-btn"
            disabled={loading}
          >
            <span className="material-symbols-outlined text-[14px]">refresh</span>
            Re-ejecutar matching con este umbral
          </button>
        </div>

        <div className="flex items-center justify-between px-7 mb-1">
          <h3 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
            {showOnlyWarn ? 'Aliases sospechosos' : 'Todos los aliases'} ({filtered.length})
          </h3>
          <button
            type="button"
            onClick={() => setShowOnlyWarn((v) => !v)}
            className="text-[10px] font-bold uppercase tracking-wider text-secondary hover:underline transition-colors"
          >
            {showOnlyWarn ? 'Mostrar todos' : 'Solo sospechosos'}
          </button>
        </div>

        <div className="or-aliases-drawer__list">
          {loading && (
            <p className="text-xs text-on-surface-variant text-center py-4">
              <span className="material-symbols-outlined animate-openrouter-spin align-middle mr-1 text-[14px]">
                progress_activity
              </span>
              Cargando aliases...
            </p>
          )}
          {!loading && filtered.length === 0 && (
            <p className="text-xs text-on-surface-variant text-center py-6 opacity-70">
              {showOnlyWarn
                ? '✓ Sin aliases sospechosos. Todo el matching automático parece correcto.'
                : 'Sin aliases registrados todavía. Aparecen tras el primer scrape exitoso.'}
            </p>
          )}
          {!loading &&
            filtered.map((alias, idx) => {
              const lvl = scoreLevel(alias.score, threshold);
              return (
                <div
                  key={`${alias.openrouter_id}-${alias.source}`}
                  className={`or-aliases-drawer__row animate-openrouter-row-fade ${
                    lvl === 'bad' ? 'or-aliases-drawer__row--warn' : ''
                  }`}
                  style={{ animationDelay: `${Math.min(idx * 25, 400)}ms` }}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-bold text-on-surface truncate">
                      {alias.openrouter_id}
                    </p>
                    <p className="text-[10px] text-on-surface-variant truncate">
                      ↔ {alias.external_name}{' '}
                      <span className="opacity-60">· {alias.source}</span>
                    </p>
                  </div>
                  <span className={`or-aliases-drawer__score or-aliases-drawer__score--${lvl}`}>
                    {(alias.score ?? 1).toFixed(2)}
                  </span>
                </div>
              );
            })}
        </div>

        <div className="or-aliases-drawer__footer">
          <button
            type="button"
            className="or-aliases-drawer__create-btn"
            onClick={onCreateAlias}
          >
            <span className="material-symbols-outlined text-[14px]">add</span>
            Crear alias manual
          </button>
          <span className="text-[10px] text-on-surface-variant self-center">
            Esc o click afuera para cerrar
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
