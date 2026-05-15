interface Props {
  onBack?: () => void;
  enabled: boolean;
  ready: boolean;
  expiredPending: number;
  reloading?: boolean;
  onReload?: () => void;
}

export default function PageHeader({ onBack, enabled, ready, expiredPending, reloading, onReload }: Props) {
  const statusLabel = !enabled ? 'Pausado' : ready ? 'Operativo' : 'Inicializando';
  const pillClass = !enabled
    ? 'cr-status-pill--neutral'
    : ready
      ? 'cr-status-pill--ok'
      : 'cr-status-pill--warn';

  return (
    <div className="flex items-center justify-between flex-shrink-0 flex-wrap gap-2">
      <div className="flex items-center gap-2 text-on-surface-variant text-label-sm">
        <button
          type="button"
          onClick={onBack}
          className="hover:text-secondary cursor-pointer transition-colors"
        >
          Plugins
        </button>
        <span className="material-symbols-outlined text-[14px]">chevron_right</span>
        <span className="text-secondary font-semibold">Code Runner</span>
        <span className={`cr-status-pill ${pillClass} ml-3`}>
          {ready && enabled && <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-cr-pulse-dot" />}
          {statusLabel}
        </span>
        {expiredPending > 0 && (
          <span className="cr-status-pill cr-status-pill--warn ml-1">
            <span className="material-symbols-outlined text-[12px]">history</span>
            {expiredPending} sesiones expiradas pendientes
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onReload}
          className="flex items-center gap-2 text-on-surface-variant hover:text-secondary transition-colors font-medium text-xs"
        >
          <span className={`material-symbols-outlined text-[16px] ${reloading ? 'animate-cr-spin' : ''}`}>
            refresh
          </span>
          <span>Recargar</span>
        </button>
      </div>
    </div>
  );
}
