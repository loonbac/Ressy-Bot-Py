import { useRef } from 'react';
import type { AudioQuality, MusicConfig } from '@/api/music';
import ToggleSwitch from './ToggleSwitch';
import './PlaybackSettingsCard.css';
import './animations.css';

interface Props {
  config: MusicConfig;
  ffmpegAvailable?: boolean;
  onChange: <K extends keyof MusicConfig>(key: K, value: MusicConfig[K]) => void;
}

const QUALITIES: Array<{ value: AudioQuality; label: string; bitrate: string; icon: string }> = [
  { value: 'standard', label: 'Estándar', bitrate: '128 kbps',     icon: 'graphic_eq' },
  { value: 'medium',   label: 'Media',    bitrate: '192-256 kbps', icon: 'equalizer' },
  { value: 'high',     label: 'Alta',     bitrate: '320 kbps',     icon: 'spa' },
];

export default function PlaybackSettingsCard({ config, ffmpegAvailable = true, onChange }: Props) {
  const groupRef = useRef<HTMLDivElement | null>(null);

  const handleQuality = (q: AudioQuality, btn: HTMLButtonElement | null) => {
    onChange('audio_quality', q);
    if (btn) {
      btn.classList.remove('animate-music-quality-glow');
      void btn.offsetWidth;
      btn.classList.add('animate-music-quality-glow');
    }
    const grp = groupRef.current;
    if (grp) {
      grp.classList.remove('animate-music-chip-bounce');
      void grp.offsetWidth;
      grp.classList.add('animate-music-chip-bounce');
    }
  };

  return (
    <div className="music-playback-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="music-playback-card__pattern" />
      <div className="relative z-10 flex flex-col h-full min-h-0">
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <div className="flex items-center gap-2">
            <span
              className="material-symbols-outlined text-secondary text-[22px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              settings_input_component
            </span>
            <span className="font-headline-md text-headline-md text-primary leading-none">
              Ajustes de Reproducción
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-label-sm uppercase tracking-wider text-tertiary">
              {config.enabled ? 'Activo' : 'Pausado'}
            </span>
            <ToggleSwitch
              checked={config.enabled}
              onChange={(v) => onChange('enabled', v)}
              size="md"
            />
          </div>
        </div>

        {!ffmpegAvailable && (
          <div className="mb-3 p-2.5 rounded-lg bg-error-container/40 border border-error/30 flex items-center gap-2 text-error text-sm flex-shrink-0">
            <span className="material-symbols-outlined text-[18px]">warning</span>
            <span>FFmpeg no detectado. Instálalo para que el bot pueda reproducir audio.</span>
          </div>
        )}

        <div className="flex-1 min-h-0 flex flex-col gap-5">
          <div>
            <p className="text-label-sm uppercase tracking-wider text-primary font-bold mb-2">
              Calidad de Audio
            </p>
            <div ref={groupRef} className="grid grid-cols-3 gap-2.5">
              {QUALITIES.map((q) => {
                const active = config.audio_quality === q.value;
                return (
                  <button
                    key={q.value}
                    type="button"
                    onClick={(e) => handleQuality(q.value, e.currentTarget)}
                    className={
                      'music-quality-option rounded-xl py-3 px-3 flex flex-col items-center gap-1 cursor-pointer ' +
                      (active ? 'music-quality-option--active' : '')
                    }
                  >
                    <span
                      className="material-symbols-outlined text-[22px]"
                      style={{ fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0" }}
                    >
                      {q.icon}
                    </span>
                    <span className="text-sm font-bold">{q.label}</span>
                    <span className="text-[10px] uppercase tracking-wider opacity-70">
                      {q.bitrate}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="text-xs text-tertiary leading-relaxed">
            Selecciona la fidelidad con la que el bot codifica el audio en los canales de voz.
            Calidad más alta consume más ancho de banda y CPU del servidor.
          </div>
        </div>
      </div>
    </div>
  );
}
