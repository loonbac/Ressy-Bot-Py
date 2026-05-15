interface Props {
  onBack?: () => void;
  nextScrapeIn?: string | null;
  autoRefresh?: boolean;
  onToggleAutoRefresh?: () => void;
  onReloadAll?: () => void;
  reloading?: boolean;
}

export default function PageHeader({
  onBack,
  nextScrapeIn,
  autoRefresh,
  onToggleAutoRefresh,
  onReloadAll,
  reloading,
}: Props) {
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
        <span className="text-secondary font-semibold">OpenRouter Prices</span>
        {nextScrapeIn ? (
          <span className="ml-3 px-3 py-1 bg-secondary-fixed text-on-secondary-fixed text-[10px] font-bold rounded-full uppercase tracking-tighter">
            Próximo scrape automático: {nextScrapeIn}
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onToggleAutoRefresh}
          className="flex items-center gap-2 text-xs text-on-surface-variant hover:text-secondary transition-colors"
        >
          <span>Auto-refresh 30s</span>
          <span
            className={`w-8 h-4 rounded-full relative cursor-pointer transition-colors ${
              autoRefresh ? 'bg-secondary' : 'bg-outline-variant/50'
            }`}
          >
            <span
              className={`absolute top-0.5 w-3 h-3 bg-white rounded-full shadow-sm transition-all ${
                autoRefresh ? 'right-0.5' : 'left-0.5'
              }`}
            />
          </span>
        </button>
        <button
          type="button"
          onClick={onReloadAll}
          className="flex items-center gap-2 text-on-surface-variant hover:text-secondary transition-colors font-medium text-xs"
        >
          <span
            className={`material-symbols-outlined text-[16px] ${
              reloading ? 'animate-openrouter-spin' : ''
            }`}
          >
            refresh
          </span>
          <span>Recargar</span>
        </button>
      </div>
    </div>
  );
}
