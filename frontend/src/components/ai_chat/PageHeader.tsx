interface Props {
  onBack?: () => void;
  ready: boolean;
  enabled: boolean;
  reloading?: boolean;
  onReload?: () => void;
}

export default function PageHeader({ onBack, ready, enabled, reloading, onReload }: Props) {
  const statusLabel = !enabled
    ? 'Desactivado'
    : ready
      ? 'En línea'
      : 'Inicializando';
  const statusColor = !enabled
    ? 'bg-outline-variant text-on-surface-variant'
    : ready
      ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
      : 'bg-amber-500/15 text-amber-700 dark:text-amber-300';

  return (
    <div className="flex items-center justify-between flex-shrink-0">
      <div className="flex items-center gap-2 text-on-surface-variant text-label-sm">
        <button
          type="button"
          onClick={onBack}
          className="hover:text-secondary cursor-pointer transition-colors"
        >
          Plugins
        </button>
        <span className="material-symbols-outlined text-[14px]">chevron_right</span>
        <span className="text-secondary font-semibold">Chat IA · MiniMax</span>
        <span
          className={`ml-3 px-3 py-1 text-[10px] font-bold rounded-full uppercase tracking-tighter ${statusColor}`}
        >
          {statusLabel}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onReload}
          className="flex items-center gap-2 text-on-surface-variant hover:text-secondary transition-colors font-medium text-xs"
        >
          <span
            className={`material-symbols-outlined text-[16px] ${reloading ? 'animate-ai-chat-spin' : ''}`}
          >
            refresh
          </span>
          <span>Recargar</span>
        </button>
      </div>
    </div>
  );
}
