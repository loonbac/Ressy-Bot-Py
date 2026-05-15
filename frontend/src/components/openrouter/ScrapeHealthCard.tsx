import { useState } from 'react';
import './ScrapeHealthCard.css';
import type { ScrapeHealth } from '@/api/openrouter';

type TriggerState = 'idle' | 'loading' | 'success' | 'error';

interface Props {
  label: string;
  source: string;
  health: ScrapeHealth | null;
  onTrigger: (source: string) => Promise<void>;
  aliasesMissed?: number;
  onOpenAliases?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  ok: 'Estable',
  error: 'Error',
  rate_limited: 'Limitado',
  unauthorized: 'Sin autorización',
  no_data: 'Sin datos',
};

function formatAge(seconds: number | null): string {
  if (seconds == null) return 'sin datos';
  if (seconds < 60) return `hace ${seconds}s`;
  if (seconds < 3600) return `hace ${Math.floor(seconds / 60)}min`;
  if (seconds < 86400) return `hace ${Math.floor(seconds / 3600)}h`;
  return `hace ${Math.floor(seconds / 86400)} días`;
}

function badgeKind(health: ScrapeHealth | null): 'ok' | 'warn' | 'error' {
  if (!health) return 'warn';
  if (health.last_status === 'ok' && !health.stale) return 'ok';
  if (health.last_status === 'ok' && health.stale) return 'warn';
  return 'error';
}

export default function ScrapeHealthCard({
  label,
  source,
  health,
  onTrigger,
  aliasesMissed,
  onOpenAliases,
}: Props) {
  const [state, setState] = useState<TriggerState>('idle');

  const handleClick = async () => {
    setState('loading');
    try {
      await onTrigger(source);
      setState('success');
      window.setTimeout(() => setState('idle'), 1500);
    } catch {
      setState('error');
      window.setTimeout(() => setState('idle'), 1500);
    }
  };

  const kind = badgeKind(health);
  const badgeText =
    kind === 'ok'
      ? 'Estable'
      : kind === 'warn'
        ? 'Advertencia'
        : STATUS_LABELS[health?.last_status ?? ''] ?? 'Error';

  return (
    <div
      className={`openrouter-scrape-card ${
        kind === 'error' ? 'animate-openrouter-glow' : ''
      }`}
    >
      <div className="flex justify-between items-center">
        <span className="font-bold text-sm text-on-surface">{label}</span>
        <span className={`openrouter-scrape-card__badge openrouter-scrape-card__badge--${kind}`}>
          <span className={`openrouter-scrape-card__dot openrouter-scrape-card__dot--${kind}`} />
          {badgeText}
        </span>
      </div>

      <div className="text-xs text-on-surface-variant space-y-1">
        <p>Último éxito: {formatAge(health?.age_seconds ?? null)}</p>
        <p>Estado: {STATUS_LABELS[health?.last_status ?? ''] ?? '—'}</p>
      </div>

      {aliasesMissed != null && aliasesMissed > 0 && (
        <button
          type="button"
          onClick={onOpenAliases}
          className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-error-container/60 text-on-error-container hover:bg-error/20 transition-colors flex items-center gap-1 self-start"
          title="Click para revisar matching de nombres"
        >
          <span className="material-symbols-outlined text-[12px]">link_off</span>
          {aliasesMissed} sin match
        </button>
      )}

      {health?.last_error && (
        <div className="openrouter-scrape-card__error animate-openrouter-row-fade">
          {health.last_error}
        </div>
      )}

      <button
        type="button"
        className={`openrouter-scrape-card__btn ${
          state === 'success' ? 'animate-openrouter-bloom' : ''
        } ${state === 'error' ? 'animate-openrouter-shake' : ''}`}
        onClick={handleClick}
        disabled={state === 'loading'}
      >
        <span
          className={`material-symbols-outlined text-[14px] ${
            state === 'loading' ? 'animate-openrouter-spin' : ''
          }`}
        >
          {state === 'success' ? 'check' : state === 'loading' ? 'progress_activity' : 'sync'}
        </span>
        {state === 'loading'
          ? 'EJECUTANDO...'
          : state === 'success'
            ? '¡EJECUTADO!'
            : state === 'error'
              ? 'ERROR'
              : 'EJECUTAR SCRAPE'}
      </button>
    </div>
  );
}
