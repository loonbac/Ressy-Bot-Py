import type { YouTubeConfig } from '@/api/youtube';
import ToggleSwitch from './ToggleSwitch';

interface Props {
  config: YouTubeConfig;
  onFilterShortsChange: (v: boolean) => void;
  onFilterPremieresChange: (v: boolean) => void;
  onFilterMinDurationChange: (v: number) => void;
}

export default function FiltersCard({
  config,
  onFilterShortsChange,
  onFilterPremieresChange,
  onFilterMinDurationChange,
}: Props) {
  return (
    <div className="bg-surface-container-lowest/60 backdrop-blur-md rounded-xl p-4 border border-white/40 shadow-sm">
      <h3 className="font-headline-md text-headline-md mb-3 flex items-center gap-2">
        <span className="material-symbols-outlined text-secondary text-[20px]">filter_list</span>
        Filtros de Contenido
      </h3>
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-sm text-on-surface-variant">Omitir Shorts</span>
          <ToggleSwitch checked={config.filter_shorts} onChange={onFilterShortsChange} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-on-surface-variant">Omitir Estrenos</span>
          <ToggleSwitch checked={config.filter_premieres} onChange={onFilterPremieresChange} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-on-surface-variant">Solo videos &gt; 5 min</span>
          <ToggleSwitch
            checked={config.filter_min_duration > 0}
            onChange={(v) => onFilterMinDurationChange(v ? 300 : 0)}
          />
        </div>
      </div>
    </div>
  );
}
