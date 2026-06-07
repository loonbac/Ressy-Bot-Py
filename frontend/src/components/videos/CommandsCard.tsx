import { ALL_COMMANDS, type VideoConfig } from '@/api/videos';
import './base.css';
import './CommandsCard.css';

interface Props {
  config: VideoConfig;
  onChange: <K extends keyof VideoConfig>(key: K, value: VideoConfig[K]) => void;
}

const COMMAND_META: Record<string, { icon: string; desc: string }> = {
  ver: { icon: 'play_circle', desc: '/ver <url> — reproduce un video en tu canal de voz' },
  parar: { icon: 'stop_circle', desc: '/parar — detiene el video de tu canal' },
};

export default function CommandsCard({ config, onChange }: Props) {
  const toggleCommand = (cmd: string) => {
    const set = new Set(config.enabled_commands);
    if (set.has(cmd)) set.delete(cmd);
    else set.add(cmd);
    onChange('enabled_commands', ALL_COMMANDS.filter((c) => set.has(c)));
  };

  return (
    <div className="videos-card p-4 h-full flex flex-col gap-3 min-h-0 animate-videos-card-enter animate-videos-stagger-4">
      <span className="videos-card__accent" />

      {/* Master enable */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-[20px]"
            style={{ color: 'var(--color-secondary)', fontVariationSettings: "'FILL' 1" }}
          >
            toggle_on
          </span>
          <h3 className="font-headline-md text-on-surface text-base">Comandos</h3>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={config.enabled}
          onClick={() => onChange('enabled', !config.enabled)}
          className={'videos-switch ' + (config.enabled ? 'videos-switch--on' : '')}
        >
          <span className="videos-switch__thumb" />
        </button>
      </div>
      <p className="text-[0.7rem] text-on-surface-variant -mt-1 flex-shrink-0">
        {config.enabled ? 'El reproductor está activo.' : 'El reproductor está desactivado.'}
      </p>

      {/* Per-command toggles */}
      <div className="flex flex-col gap-2 flex-1 min-h-0 overflow-y-auto pr-1">
        {ALL_COMMANDS.map((cmd) => {
          const enabled = config.enabled_commands.includes(cmd);
          const meta = COMMAND_META[cmd];
          return (
            <button
              key={cmd}
              type="button"
              onClick={() => toggleCommand(cmd)}
              className={'videos-cmd-row ' + (enabled ? 'videos-cmd-row--on' : '')}
            >
              <span
                className="material-symbols-outlined text-[20px]"
                style={{ fontVariationSettings: enabled ? "'FILL' 1" : "'FILL' 0" }}
              >
                {meta?.icon ?? 'terminal'}
              </span>
              <div className="flex-1 text-left min-w-0">
                <div className="font-semibold text-sm">/{cmd}</div>
                <div className="text-[0.7rem] text-on-surface-variant truncate">{meta?.desc}</div>
              </div>
              <span
                className={'videos-cmd-check ' + (enabled ? 'videos-cmd-check--on' : '')}
              >
                <span className="material-symbols-outlined text-[16px]">
                  {enabled ? 'check' : 'close'}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
