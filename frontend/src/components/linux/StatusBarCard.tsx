import type { LinuxProduct, LinuxSummary } from '@/api/linux';
import './StatusBarCard.css';
import './animations.css';

interface Props {
  products: LinuxProduct[];
  summary: LinuxSummary | null;
  lastSync: string;
  refreshing: boolean;
  onRefresh: () => void;
  onScrollToSettings: () => void;
}

export default function StatusBarCard({
  products,
  summary,
  lastSync,
  refreshing,
  onRefresh,
  onScrollToSettings,
}: Props) {
  const distros = products.length;
  const versions = summary?.total_releases ?? 0;
  const expiringSoon = summary?.expiring_soon.length ?? 0;
  const expired = summary?.expired.length ?? 0;

  return (
    <div className="linux-status-bar rounded-xl p-6 flex flex-col lg:flex-row justify-between items-center gap-5 animate-linux-card-enter animate-linux-stagger-1">
      <div className="flex flex-col">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-secondary text-[28px] animate-linux-icon-pop"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            update
          </span>
          <h2 className="font-headline-md text-headline-md text-primary">Linux Updates</h2>
        </div>
        <p className="text-label-sm text-on-surface-variant mt-1">
          Última sincronización: <span className="font-bold">{lastSync}</span>
        </p>
      </div>

      <div className="flex flex-wrap gap-7 justify-center">
        <Stat label="Distribuciones" value={distros} delay={1} />
        <Stat label="Versiones" value={versions} delay={2} />
        <Stat label="Próximas EOL" value={expiringSoon} delay={3} tone="warning" />
        <Stat label="Expiradas" value={expired} delay={4} tone="error" />
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="linux-status-bar__refresh flex items-center gap-2 px-5 py-2 rounded-full font-bold text-sm transition-all disabled:opacity-60"
        >
          <span
            className={`material-symbols-outlined text-[18px] ${refreshing ? 'animate-linux-sync-spin' : ''}`}
          >
            sync
          </span>
          <span>{refreshing ? 'Refrescando...' : 'Refrescar ahora'}</span>
        </button>
        <button
          type="button"
          onClick={onScrollToSettings}
          className="linux-status-bar__configure flex items-center gap-2 px-5 py-2 rounded-full font-bold text-sm transition-all"
        >
          <span className="material-symbols-outlined text-[18px]">notifications_active</span>
          <span>Configurar</span>
        </button>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  delay,
  tone,
}: {
  label: string;
  value: number;
  delay: number;
  tone?: 'warning' | 'error';
}) {
  const valueClass =
    tone === 'error'
      ? 'linux-status-bar__stat-error'
      : tone === 'warning'
        ? 'linux-status-bar__stat-warning'
        : 'linux-status-bar__stat-default';
  const labelClass =
    tone === 'error'
      ? 'text-error'
      : tone === 'warning'
        ? 'text-secondary'
        : 'text-on-surface-variant';

  return (
    <div
      className={`text-center animate-linux-stat-count animate-linux-stagger-${delay}`}
      key={`${label}-${value}`}
    >
      <p className={`text-headline-md font-display ${valueClass}`}>{value}</p>
      <p className={`text-label-sm uppercase tracking-wider ${labelClass}`}>{label}</p>
    </div>
  );
}
