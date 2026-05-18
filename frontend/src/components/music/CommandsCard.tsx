import { useMemo, useRef } from 'react';
import { ALL_COMMANDS, type MusicConfig } from '@/api/music';
import ToggleSwitch from './ToggleSwitch';
import './CommandsCard.css';
import './animations.css';

interface Props {
  config: MusicConfig;
  onChange: <K extends keyof MusicConfig>(key: K, value: MusicConfig[K]) => void;
  layout?: 'grid' | 'list';
  hideHeader?: boolean;
}

interface CommandMeta {
  name: string;
  description: string;
  icon: string;
}

const COMMAND_META: Record<string, CommandMeta> = {
  play:       { name: 'play',       icon: 'play_circle', description: 'Reproduce música desde una URL o búsqueda.' },
  stop:       { name: 'stop',       icon: 'stop_circle', description: 'Detiene la reproducción y limpia la cola.' },
  queue:      { name: 'queue',      icon: 'queue_music', description: 'Muestra la cola de canciones.' },
  nowplaying: { name: 'nowplaying', icon: 'graphic_eq',  description: 'Muestra la canción actual con detalles.' },
};

export default function CommandsCard({
  config,
  onChange,
  layout = 'grid',
  hideHeader = false,
}: Props) {
  const enabledSet = useMemo(
    () => new Set(config.enabled_commands),
    [config.enabled_commands],
  );
  const cardRef = useRef<HTMLDivElement | null>(null);

  const toggle = (cmd: string, tile: HTMLDivElement | null) => {
    const next = new Set(enabledSet);
    if (next.has(cmd)) next.delete(cmd);
    else next.add(cmd);
    onChange('enabled_commands', Array.from(next));
    if (tile) {
      tile.classList.remove('animate-music-command-flip');
      void tile.offsetWidth;
      tile.classList.add('animate-music-command-flip');
    }
  };

  const setAll = (enable: boolean) => {
    onChange('enabled_commands', enable ? [...ALL_COMMANDS] : []);
    const card = cardRef.current;
    if (card) {
      card.classList.remove('animate-music-chip-bounce');
      void card.offsetWidth;
      card.classList.add('animate-music-chip-bounce');
    }
  };

  const wrapperClass = hideHeader
    ? 'h-full flex flex-col min-h-0 overflow-hidden'
    : 'music-commands-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden';

  return (
    <div ref={cardRef} className={wrapperClass}>
      {!hideHeader && (
        <div className="flex items-center justify-between mb-3 flex-shrink-0">
          <div className="flex items-center gap-2">
            <span
              className="material-symbols-outlined text-secondary text-[22px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              terminal
            </span>
            <span className="font-headline-md text-headline-md text-primary leading-none">
              Comandos de Música
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] uppercase tracking-wider text-tertiary">
              {enabledSet.size} / {ALL_COMMANDS.length}
            </span>
            <button
              type="button"
              onClick={() => setAll(true)}
              className="text-[11px] uppercase tracking-wider font-bold text-primary hover:text-secondary transition-colors px-2 py-1 rounded hover:bg-primary-container/30"
            >
              Activar todos
            </button>
            <button
              type="button"
              onClick={() => setAll(false)}
              className="text-[11px] uppercase tracking-wider font-bold text-tertiary hover:text-error transition-colors px-2 py-1 rounded hover:bg-error-container/30"
            >
              Ninguno
            </button>
          </div>
        </div>
      )}

      {hideHeader && (
        <div className="flex items-center justify-end gap-2 mb-2 flex-shrink-0">
          <button
            type="button"
            onClick={() => setAll(true)}
            className="text-[11px] uppercase tracking-wider font-bold text-primary hover:text-secondary transition-colors px-2 py-1 rounded hover:bg-primary-container/30"
          >
            Activar todos
          </button>
          <button
            type="button"
            onClick={() => setAll(false)}
            className="text-[11px] uppercase tracking-wider font-bold text-tertiary hover:text-error transition-colors px-2 py-1 rounded hover:bg-error-container/30"
          >
            Ninguno
          </button>
        </div>
      )}

      {layout === 'grid' ? (
        <div className="flex-1 min-h-0 overflow-y-auto pr-1 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 auto-rows-min">
          {ALL_COMMANDS.map((cmd, idx) => {
            const meta = COMMAND_META[cmd];
            const active = enabledSet.has(cmd);
            return (
              <div
                key={cmd}
                onClick={(e) => toggle(cmd, e.currentTarget)}
                className={
                  'music-command-tile rounded-xl p-3.5 flex flex-col justify-between gap-2 cursor-pointer animate-music-track-slide-in ' +
                  (active ? 'music-command-tile--active' : 'music-command-tile--inactive')
                }
                style={{ animationDelay: `${idx * 25}ms` }}
              >
                <div className="flex justify-between items-start gap-2">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="material-symbols-outlined text-[18px]"
                      style={{
                        color: active ? 'var(--color-secondary)' : 'var(--color-tertiary)',
                        fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0",
                      }}
                    >
                      {meta.icon}
                    </span>
                    <span className="music-command-tile__chip px-2 py-0.5 rounded-full text-[11px] font-bold">
                      /{meta.name}
                    </span>
                  </div>
                  <div onClick={(e) => e.stopPropagation()}>
                    <ToggleSwitch
                      checked={active}
                      onChange={(v) => {
                        const next = new Set(enabledSet);
                        if (v) next.add(cmd);
                        else next.delete(cmd);
                        onChange('enabled_commands', Array.from(next));
                      }}
                      size="sm"
                    />
                  </div>
                </div>
                <p className="text-[11px] text-tertiary leading-snug">{meta.description}</p>
              </div>
            );
          })}
        </div>
      ) : (
        <ul className="flex-1 min-h-0 overflow-y-auto pr-1 flex flex-col gap-2">
          {ALL_COMMANDS.map((cmd, idx) => {
            const meta = COMMAND_META[cmd];
            const active = enabledSet.has(cmd);
            return (
              <li
                key={cmd}
                onClick={(e) => toggle(cmd, e.currentTarget as unknown as HTMLDivElement)}
                className={
                  'music-command-tile rounded-xl px-4 py-3 flex items-center gap-3 cursor-pointer animate-music-track-slide-in ' +
                  (active ? 'music-command-tile--active' : 'music-command-tile--inactive')
                }
                style={{ animationDelay: `${idx * 25}ms` }}
              >
                <span
                  className="material-symbols-outlined text-[20px] flex-shrink-0"
                  style={{
                    color: active ? 'var(--color-secondary)' : 'var(--color-tertiary)',
                    fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0",
                  }}
                >
                  {meta.icon}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="music-command-tile__chip px-2 py-0.5 rounded-full text-[11px] font-bold">
                      /{meta.name}
                    </span>
                    <span
                      className={
                        'text-[10px] uppercase tracking-wider font-bold ' +
                        (active ? 'text-secondary' : 'text-tertiary')
                      }
                    >
                      {active ? 'Activo' : 'Pausado'}
                    </span>
                  </div>
                  <p className="text-[12px] text-tertiary leading-snug">{meta.description}</p>
                </div>
                <div onClick={(e) => e.stopPropagation()} className="flex-shrink-0">
                  <ToggleSwitch
                    checked={active}
                    onChange={(v) => {
                      const next = new Set(enabledSet);
                      if (v) next.add(cmd);
                      else next.delete(cmd);
                      onChange('enabled_commands', Array.from(next));
                    }}
                    size="md"
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
