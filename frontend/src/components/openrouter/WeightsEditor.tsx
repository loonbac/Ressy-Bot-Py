import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import './WeightsEditor.css';
import type {
  PhaseSummary,
  PhaseWeightEntry,
} from '@/api/openrouter';
import { fetchPhaseWeights, updatePhaseWeights } from '@/api/openrouter';

interface Props {
  open: boolean;
  phase: PhaseSummary | null;
  onClose: () => void;
  onSaved?: (phase: string) => void;
}

const SLUG_LABELS: Record<string, string> = {
  ifbench: 'IFBench',
  multichallenge: 'MultiChallenge',
  tau2_telecom: 'τ²-Telecom',
  bfcl_v3: 'BFCL v3',
  bfcl_parallel: 'BFCL Parallel',
  aa_intelligence_index: 'AA Intelligence Index',
  ruler: 'RULER',
  longbench: 'LongBench',
  input_cache_read_ratio: 'Cache Read Ratio',
  supports_reasoning_effort: 'Reasoning Effort',
  supports_verbosity: 'Verbosity',
};

const RESERVED_SLUGS = new Set([
  'multichallenge',
  'ruler',
  'longbench',
]);

export default function WeightsEditor({ open, phase, onClose, onSaved }: Props) {
  const [weights, setWeights] = useState<PhaseWeightEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [originalSnapshot, setOriginalSnapshot] = useState<PhaseWeightEntry[]>([]);

  useEffect(() => {
    if (!open || !phase) return;
    const load = async () => {
      setLoading(true);
      try {
        const data = await fetchPhaseWeights(phase.slug);
        setWeights(data);
        setOriginalSnapshot(data.map((w) => ({ ...w })));
      } catch {
        setWeights([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [open, phase]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  const sum = useMemo(
    () => weights.reduce((acc, w) => acc + w.weight, 0),
    [weights],
  );
  const sumOk = Math.abs(sum - 1.0) < 1e-6;
  const sumPct = (sum * 100).toFixed(1);

  const dirty = useMemo(() => {
    if (weights.length !== originalSnapshot.length) return true;
    for (let i = 0; i < weights.length; i++) {
      if (Math.abs(weights[i].weight - originalSnapshot[i].weight) > 1e-9) return true;
    }
    return false;
  }, [weights, originalSnapshot]);

  const setWeight = (slug: string, value: number) => {
    setWeights((prev) =>
      prev.map((w) =>
        w.benchmark_slug === slug ? { ...w, weight: Math.max(0, Math.min(1, value)) } : w,
      ),
    );
  };

  const resetToOriginal = () => {
    setWeights(originalSnapshot.map((w) => ({ ...w })));
    setFeedback(null);
  };

  const normalizeToOne = () => {
    if (sum === 0) return;
    setWeights((prev) =>
      prev.map((w) => ({ ...w, weight: w.weight / sum })),
    );
  };

  const handleSave = async () => {
    if (!phase || !sumOk) return;
    setSaving(true);
    setFeedback(null);
    try {
      await updatePhaseWeights(phase.slug, weights);
      setOriginalSnapshot(weights.map((w) => ({ ...w })));
      setFeedback('✓ Pesos guardados');
      onSaved?.(phase.slug);
      window.setTimeout(() => setFeedback(null), 2400);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  if (!open || !phase) return null;

  return createPortal(
    <div
      className="or-weights-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="or-weights-modal" role="dialog" aria-modal="true">
        <div className="or-weights-modal__header">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-on-surface-variant font-bold mb-1">
              Editor de pesos
            </p>
            <h2 className="font-display text-headline-lg text-primary leading-none">
              {phase.label}
            </h2>
            <p className="text-xs text-on-surface-variant mt-1">
              Ajusta los pesos para que la suma sea exactamente 100%. Los benchmarks
              reservados (sin datos disponibles) se mantienen en 0%.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`or-weights-modal__sum-pill ${
                sumOk
                  ? 'or-weights-modal__sum-pill--ok'
                  : 'or-weights-modal__sum-pill--bad'
              }`}
            >
              <span className="material-symbols-outlined text-[14px]">
                {sumOk ? 'check_circle' : 'error'}
              </span>
              Total: {sumPct}%
            </span>
            <button
              type="button"
              className="or-weights-modal__close"
              onClick={onClose}
              aria-label="Cerrar"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>

        <div className="or-weights-modal__body">
          {loading && (
            <p className="text-xs text-on-surface-variant text-center py-6">
              <span className="material-symbols-outlined animate-openrouter-spin align-middle mr-1 text-[14px]">
                progress_activity
              </span>
              Cargando pesos actuales...
            </p>
          )}
          {!loading && weights.length === 0 && (
            <p className="text-xs text-on-surface-variant text-center py-6 opacity-70">
              Sin weights cargados. Esta fase puede no tener perfil en DB.
            </p>
          )}
          {!loading &&
            weights.map((w, idx) => {
              const label = SLUG_LABELS[w.benchmark_slug] ?? w.benchmark_slug;
              const isReserved = RESERVED_SLUGS.has(w.benchmark_slug);
              return (
                <div
                  key={w.benchmark_slug}
                  className={`or-weights-modal__row animate-openrouter-row-fade ${
                    w.is_feature_factor ? 'or-weights-modal__row--feature' : ''
                  } ${isReserved ? 'or-weights-modal__row--reserved' : ''}`}
                  style={{ animationDelay: `${idx * 30}ms` }}
                >
                  <div className="or-weights-modal__slug min-w-0">
                    <span className="truncate">{label}</span>
                    {w.is_feature_factor && (
                      <span className="or-weights-modal__slug-badge or-weights-modal__slug-badge--feature">
                        Feature
                      </span>
                    )}
                    {isReserved && (
                      <span className="or-weights-modal__slug-badge or-weights-modal__slug-badge--reserved">
                        Sin datos
                      </span>
                    )}
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.01}
                    value={w.weight}
                    onChange={(e) =>
                      setWeight(w.benchmark_slug, Number(e.target.value))
                    }
                    className="or-weights-modal__slider"
                  />
                  <span className="or-weights-modal__value">
                    {(w.weight * 100).toFixed(0)}%
                  </span>
                </div>
              );
            })}
        </div>

        <div className="or-weights-modal__footer">
          <div className="flex items-center gap-2 text-xs">
            {feedback && (
              <span
                className={`font-bold ${
                  feedback.startsWith('✓') ? 'text-green-600' : 'text-error'
                }`}
              >
                {feedback}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className="or-weights-modal__btn or-weights-modal__btn--secondary"
              onClick={normalizeToOne}
              disabled={loading || sum === 0 || sumOk}
              title="Escalar todos los pesos para que sumen 100%"
            >
              <span className="material-symbols-outlined text-[14px]">
                tune
              </span>
              Normalizar
            </button>
            <button
              type="button"
              className="or-weights-modal__btn or-weights-modal__btn--secondary"
              onClick={resetToOriginal}
              disabled={loading || !dirty}
            >
              <span className="material-symbols-outlined text-[14px]">undo</span>
              Restaurar
            </button>
            <button
              type="button"
              className="or-weights-modal__btn or-weights-modal__btn--primary"
              onClick={handleSave}
              disabled={loading || saving || !sumOk || !dirty}
            >
              <span
                className={`material-symbols-outlined text-[14px] ${
                  saving ? 'animate-openrouter-spin' : ''
                }`}
              >
                {saving ? 'progress_activity' : 'save'}
              </span>
              {saving ? 'Guardando...' : 'Guardar pesos'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
