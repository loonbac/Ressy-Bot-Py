import { useMemo } from 'react';
import type { MusicConfig, MusicVoiceChannel } from '@/api/music';
import './AllowedChannelsCard.css';
import './animations.css';

interface Props {
  config: MusicConfig;
  channels: MusicVoiceChannel[];
  onChange: <K extends keyof MusicConfig>(key: K, value: MusicConfig[K]) => void;
}

export default function AllowedChannelsCard({ config, channels, onChange }: Props) {
  const allowedSet = useMemo(
    () => new Set(config.allowed_channel_ids),
    [config.allowed_channel_ids],
  );

  const allAllowed = allowedSet.size === 0 || allowedSet.size === channels.length;

  const toggle = (id: string, row: HTMLLabelElement | null) => {
    const next = new Set(allowedSet);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange('allowed_channel_ids', Array.from(next));
    if (row) {
      row.classList.remove('animate-music-channel-pop');
      void row.offsetWidth;
      row.classList.add('animate-music-channel-pop');
    }
  };

  const setAll = (enable: boolean) => {
    onChange('allowed_channel_ids', enable ? channels.map((c) => c.id) : []);
  };

  return (
    <div className="music-channels-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-secondary text-[22px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            record_voice_over
          </span>
          <span className="font-headline-md text-headline-md text-primary leading-none">
            Canales Permitidos
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setAll(true)}
            className="text-[11px] uppercase tracking-wider font-bold text-primary hover:text-secondary transition-colors px-2 py-1 rounded hover:bg-primary-container/30"
          >
            Todos
          </button>
          <span className="text-tertiary text-[11px]">·</span>
          <button
            type="button"
            onClick={() => setAll(false)}
            className="text-[11px] uppercase tracking-wider font-bold text-tertiary hover:text-error transition-colors px-2 py-1 rounded hover:bg-error-container/30"
          >
            Ninguno
          </button>
        </div>
      </div>

      <p className="text-xs text-tertiary mb-3 flex-shrink-0 leading-relaxed">
        Limita los canales de voz donde el bot puede entrar a reproducir música. Si dejas
        todos sin marcar, el bot acepta cualquier canal del servidor configurado.
      </p>

      {channels.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-tertiary text-sm">
          <span className="material-symbols-outlined text-3xl opacity-50">voice_chat</span>
          <span>No hay canales de voz disponibles.</span>
        </div>
      ) : (
        <div className="music-channels-card__scroll flex-1 min-h-0 overflow-y-auto pr-1 space-y-2">
          {channels.map((ch, idx) => {
            const active = allowedSet.has(ch.id) || allAllowed;
            return (
              <label
                key={ch.id}
                onClick={(e) => toggle(ch.id, e.currentTarget)}
                className={
                  'music-channel-row flex items-center justify-between p-3 rounded-xl animate-music-track-slide-in ' +
                  (allowedSet.has(ch.id) ? 'music-channel-row--active' : '')
                }
                style={{ animationDelay: `${idx * 30}ms` }}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span
                    className="material-symbols-outlined text-outline text-[20px] flex-shrink-0"
                    style={{ fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0" }}
                  >
                    volume_up
                  </span>
                  <span className="font-medium text-on-surface text-sm truncate">{ch.name}</span>
                </div>
                <span className="music-channel-row__check flex-shrink-0">
                  {allowedSet.has(ch.id) && (
                    <span
                      className="material-symbols-outlined text-white text-[14px]"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      check
                    </span>
                  )}
                </span>
              </label>
            );
          })}
        </div>
      )}

      <div className="mt-3 pt-2 border-t border-outline-variant/20 text-[11px] text-tertiary flex items-center justify-between flex-shrink-0">
        <span>
          {allowedSet.size === 0
            ? `Todos los canales (${channels.length})`
            : `${allowedSet.size} de ${channels.length} permitidos`}
        </span>
        <span className="material-symbols-outlined text-[14px]">filter_alt</span>
      </div>
    </div>
  );
}
