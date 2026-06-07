import type { VideoConfig } from '@/api/videos';
import './base.css';
import './PlaybackSettingsCard.css';

interface Props {
  config: VideoConfig;
  onChange: <K extends keyof VideoConfig>(key: K, value: VideoConfig[K]) => void;
}

const RESOLUTIONS: { label: string; w: number; h: number }[] = [
  { label: '480p', w: 854, h: 480 },
  { label: '720p', w: 1280, h: 720 },
  { label: '1080p', w: 1920, h: 1080 },
];

const FPS_OPTIONS = [24, 30, 60];

export default function PlaybackSettingsCard({ config, onChange }: Props) {
  const activeRes = RESOLUTIONS.find((r) => r.w === config.width && r.h === config.height);

  return (
    <div className="videos-card p-4 h-full flex flex-col gap-3 min-h-0 overflow-y-auto animate-videos-card-enter animate-videos-stagger-3">
      <span className="videos-card__accent" />
      <div className="flex items-center gap-2 flex-shrink-0">
        <span
          className="material-symbols-outlined text-[20px]"
          style={{ color: 'var(--color-secondary)', fontVariationSettings: "'FILL' 1" }}
        >
          tune
        </span>
        <h3 className="font-headline-md text-on-surface text-base">Calidad de transmisión</h3>
      </div>

      {/* Resolution */}
      <div className="flex-shrink-0">
        <label className="text-xs uppercase tracking-wide text-on-surface-variant">Resolución</label>
        <div className="grid grid-cols-3 gap-2 mt-1">
          {RESOLUTIONS.map((r) => {
            const active = activeRes?.label === r.label;
            return (
              <button
                key={r.label}
                type="button"
                onClick={() => {
                  onChange('width', r.w);
                  onChange('height', r.h);
                }}
                className={'videos-res-option py-2 ' + (active ? 'videos-res-option--active' : '')}
              >
                {r.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* FPS */}
      <div className="flex-shrink-0">
        <label className="text-xs uppercase tracking-wide text-on-surface-variant">FPS</label>
        <div className="grid grid-cols-3 gap-2 mt-1">
          {FPS_OPTIONS.map((f) => {
            const active = config.fps === f;
            return (
              <button
                key={f}
                type="button"
                onClick={() => onChange('fps', f)}
                className={'videos-res-option py-2 ' + (active ? 'videos-res-option--active' : '')}
              >
                {f}
              </button>
            );
          })}
        </div>
      </div>

      {/* Bitrate */}
      <div className="grid grid-cols-2 gap-3 flex-shrink-0">
        <NumField
          label="Bitrate (kbps)"
          value={config.bitrate}
          min={500}
          max={8000}
          step={250}
          onChange={(v) => onChange('bitrate', v)}
        />
        <NumField
          label="Bitrate máx (kbps)"
          value={config.bitrate_max}
          min={500}
          max={12000}
          step={250}
          onChange={(v) => onChange('bitrate_max', v)}
        />
      </div>

      {/* Manager URL */}
      <div className="flex-shrink-0 mt-auto">
        <label className="text-xs uppercase tracking-wide text-on-surface-variant">
          URL del worker-manager
        </label>
        <input
          type="text"
          value={config.manager_url}
          onChange={(e) => onChange('manager_url', e.target.value)}
          placeholder="http://video-worker:8081"
          className="videos-input w-full px-3 py-2 text-sm mt-1"
          spellCheck={false}
        />
      </div>
    </div>
  );
}

function NumField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="text-xs uppercase tracking-wide text-on-surface-variant">{label}</label>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const n = parseInt(e.target.value, 10);
          if (!Number.isNaN(n)) onChange(Math.max(min, Math.min(max, n)));
        }}
        className="videos-input w-full px-3 py-2 text-sm mt-1"
      />
    </div>
  );
}
