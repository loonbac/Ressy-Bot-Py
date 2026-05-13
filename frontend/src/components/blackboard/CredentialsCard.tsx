import { useState } from 'react';
import type { BlackboardConfig } from '@/api/blackboard';
import ToggleSwitch from './ToggleSwitch';
import './CredentialsCard.css';
import './animations.css';

interface Props {
  config: BlackboardConfig;
  onChange: <K extends keyof BlackboardConfig>(key: K, value: BlackboardConfig[K]) => void;
}

export default function CredentialsCard({ config, onChange }: Props) {
  const [showPass, setShowPass] = useState(false);

  return (
    <div className="bb-credentials-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-secondary text-[22px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            vpn_key
          </span>
          <span className="font-headline-md text-headline-md text-primary leading-none">
            Credenciales Blackboard
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

      <div className="grid grid-cols-1 gap-3 flex-1 min-h-0 overflow-y-auto pr-1">
        <div>
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            URL Blackboard
          </label>
          <input
            type="text"
            value={config.blackboard_url}
            onChange={(e) => onChange('blackboard_url', e.target.value)}
            placeholder="https://senati.blackboard.com"
            className="bb-credentials-card__input w-full rounded-lg py-2.5 px-3 text-sm font-body-md"
          />
        </div>

        <div>
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            Correo / Usuario
          </label>
          <input
            type="email"
            value={config.blackboard_user}
            onChange={(e) => onChange('blackboard_user', e.target.value)}
            placeholder="tu_correo@senati.pe"
            autoComplete="username"
            className="bb-credentials-card__input w-full rounded-lg py-2.5 px-3 text-sm font-body-md"
          />
        </div>

        <div>
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            Contraseña
          </label>
          <div className="relative">
            <input
              type={showPass ? 'text' : 'password'}
              value={config.blackboard_pass}
              onChange={(e) => onChange('blackboard_pass', e.target.value)}
              placeholder="••••••••••••"
              autoComplete="current-password"
              className="bb-credentials-card__input w-full rounded-lg py-2.5 pl-3 pr-10 text-sm font-body-md"
            />
            <button
              type="button"
              onClick={() => setShowPass((v) => !v)}
              className="bb-credentials-card__reveal absolute right-2 top-1/2 -translate-y-1/2 p-1"
              aria-label={showPass ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            >
              <span className="material-symbols-outlined text-[20px]">
                {showPass ? 'visibility_off' : 'visibility'}
              </span>
            </button>
          </div>
          <p className="text-[10px] text-tertiary mt-1 italic">
            Se almacena cifrada localmente. Solo el bot la usa.
          </p>
        </div>
      </div>
    </div>
  );
}
