import type { WelcomeConfig } from '@/api/welcome';
import ToggleSwitch from './ToggleSwitch';
import './AdvancedCard.css';

interface Props {
  config: WelcomeConfig;
  onChange: <K extends keyof WelcomeConfig>(key: K, value: WelcomeConfig[K]) => void;
}

const OPTIONS: Array<{
  key: 'dm_enabled' | 'delete_previous';
  icon: string;
  label: string;
  hint: string;
}> = [
  {
    key: 'dm_enabled',
    icon: 'mail',
    label: 'Enviar por DM',
    hint: 'Privado al usuario',
  },
  {
    key: 'delete_previous',
    icon: 'delete_sweep',
    label: 'Borrar anterior',
    hint: 'Solo la más reciente',
  },
];

export default function AdvancedCard({ config, onChange }: Props) {
  return (
    <div className="welcome-advanced-card rounded-2xl p-4 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <h3 className="font-headline-md text-headline-md text-primary mb-3 flex items-center gap-2 flex-shrink-0 leading-none">
        <span className="material-symbols-outlined text-[20px]">settings_suggest</span>
        Avanzado
      </h3>
      <div className="flex flex-col gap-2 flex-1 min-h-0 overflow-y-auto">
        {OPTIONS.map((opt) => {
          const checked = Boolean(config[opt.key]);
          return (
            <div
              key={opt.key}
              className="welcome-advanced-card__item flex items-center justify-between gap-2 p-2.5 rounded-xl"
            >
              <div className="flex items-center gap-2 min-w-0">
                <div
                  className={
                    'welcome-advanced-card__icon w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ' +
                    (checked ? 'is-active' : '')
                  }
                >
                  <span
                    className="material-symbols-outlined text-[20px]"
                    style={checked ? { fontVariationSettings: "'FILL' 1" } : undefined}
                  >
                    {opt.icon}
                  </span>
                </div>
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-bold text-on-surface leading-tight truncate">
                    {opt.label}
                  </span>
                  <span className="text-[10px] text-tertiary leading-tight truncate">
                    {opt.hint}
                  </span>
                </div>
              </div>
              <ToggleSwitch
                checked={checked}
                onChange={(v) => onChange(opt.key, v)}
                size="sm"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
