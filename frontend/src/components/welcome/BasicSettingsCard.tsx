import { useRef } from 'react';
import type { WelcomeConfig, WelcomeDiscordChannel } from '@/api/welcome';
import ToggleSwitch from './ToggleSwitch';
import './BasicSettingsCard.css';
import './animations.css';

interface Props {
  config: WelcomeConfig;
  channels: WelcomeDiscordChannel[];
  onChange: <K extends keyof WelcomeConfig>(key: K, value: WelcomeConfig[K]) => void;
}

const PLACEHOLDERS: Array<{ token: string; help: string }> = [
  { token: '{user}', help: 'Menciona al usuario (ping)' },
  { token: '{user_name}', help: 'Nombre del usuario (texto plano)' },
  { token: '{server}', help: 'Nombre del servidor' },
  { token: '{member_count}', help: 'Cantidad de miembros' },
];

export default function BasicSettingsCard({ config, channels, onChange }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const insertToken = (token: string, btn: HTMLButtonElement | null) => {
    onChange('welcome_message', `${config.welcome_message}${token}`);
    if (btn) {
      btn.classList.remove('animate-welcome-chip-bounce');
      void btn.offsetWidth;
      btn.classList.add('animate-welcome-chip-bounce');
    }
    if (textareaRef.current) {
      const ta = textareaRef.current;
      ta.classList.remove('animate-welcome-textarea-glow');
      void ta.offsetWidth;
      ta.classList.add('animate-welcome-textarea-glow');
    }
  };

  return (
    <div className="welcome-basic-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-secondary text-[22px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            tune
          </span>
          <span className="font-headline-md text-headline-md text-primary leading-none">
            Editor del Embed
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

      <div className="grid grid-cols-2 gap-3 mb-3 flex-shrink-0">
        <div>
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            Canal de Destino
          </label>
          <div className="relative">
            <select
              className="welcome-basic-card__select w-full rounded-lg py-2.5 px-3 text-sm appearance-none cursor-pointer"
              value={config.welcome_channel_id ?? ''}
              onChange={(e) => onChange('welcome_channel_id', e.target.value)}
            >
              <option value="">Seleccionar canal...</option>
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.name}
                </option>
              ))}
            </select>
            <span className="material-symbols-outlined absolute right-2.5 top-1/2 -translate-y-1/2 text-outline pointer-events-none text-[20px]">
              expand_more
            </span>
          </div>
        </div>

        <div>
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            Título del Embed
          </label>
          <input
            type="text"
            value={config.embed_title}
            onChange={(e) => onChange('embed_title', e.target.value)}
            className="welcome-basic-card__input w-full rounded-lg py-2.5 px-3 text-sm"
            placeholder="Bienvenid@ {user_name} a..."
          />
        </div>
      </div>

      <div className="flex flex-col flex-1 min-h-0">
        <div className="flex justify-between items-center mb-1.5 flex-wrap gap-2 flex-shrink-0">
          <label className="text-label-sm uppercase tracking-wider text-primary font-bold">
            Descripción
          </label>
          <div className="flex gap-1.5 flex-wrap">
            {PLACEHOLDERS.map((p) => (
              <button
                key={p.token}
                type="button"
                title={p.help}
                onClick={(e) => insertToken(p.token, e.currentTarget)}
                className="welcome-basic-card__chip px-2 py-0.5 text-[10px] rounded font-bold cursor-pointer transition-colors font-mono"
              >
                {p.token}
              </button>
            ))}
          </div>
        </div>
        <textarea
          ref={textareaRef}
          className="welcome-basic-card__textarea flex-1 min-h-0 w-full rounded-lg p-3 text-sm leading-relaxed resize-none font-body-md"
          placeholder="Escribe la descripción del embed de bienvenida..."
          value={config.welcome_message}
          onChange={(e) => onChange('welcome_message', e.target.value)}
        />
      </div>
    </div>
  );
}
