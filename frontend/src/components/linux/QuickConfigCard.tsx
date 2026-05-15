import type { LinuxConfig } from '@/api/linux';
import './QuickConfigCard.css';
import './animations.css';

interface Props {
  config: LinuxConfig;
  onChange: <K extends keyof LinuxConfig>(key: K, value: LinuxConfig[K]) => void;
  onSendTest: () => void;
  testing: boolean;
  testFeedback: 'idle' | 'success' | 'error';
}

export default function QuickConfigCard({
  config,
  onChange,
  onSendTest,
  testing,
  testFeedback,
}: Props) {
  return (
    <div className="linux-quick-config rounded-xl p-7 flex flex-col gap-5 h-full w-full flex-1 animate-linux-card-enter animate-linux-stagger-3">
      <h3 className="font-headline-md text-headline-md text-primary flex items-center gap-2">
        <span className="material-symbols-outlined text-secondary text-[24px]">tune</span>
        Configuración rápida
      </h3>

      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <label className="text-label-sm font-bold text-on-surface-variant uppercase tracking-wider">
            Umbral de aviso
          </label>
          <span className="linux-quick-config__chip animate-linux-chip-bounce" key={config.eol_warning_days}>
            {config.eol_warning_days} días
          </span>
        </div>
        <input
          type="range"
          min={7}
          max={180}
          value={config.eol_warning_days}
          onChange={(e) => onChange('eol_warning_days', Number(e.target.value))}
          className="linux-quick-config__slider w-full"
        />
        <p className="text-[12px] text-on-surface-variant italic">
          Recibirás una notificación cuando queden menos días que el umbral marcado.
        </p>
      </div>

      <div className="space-y-3">
        <label className="text-label-sm font-bold text-on-surface-variant uppercase tracking-wider">
          Intervalo de refresh
        </label>
        <select
          value={config.refresh_interval_hours}
          onChange={(e) => onChange('refresh_interval_hours', Number(e.target.value))}
          className="linux-quick-config__select w-full px-3 py-2 rounded-lg"
        >
          <option value={6}>Cada 6 horas</option>
          <option value={12}>Cada 12 horas</option>
          <option value={24}>Diario (24h)</option>
          <option value={168}>Semanal</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="text-label-sm font-bold text-on-surface-variant uppercase tracking-wider">
          Estado del scheduler
        </label>
        <label className="linux-quick-config__toggle flex items-center justify-between gap-3 p-3 rounded-lg cursor-pointer">
          <span className="flex items-center gap-2 text-on-surface">
            <span
              className="material-symbols-outlined text-[20px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              {config.enabled ? 'play_circle' : 'pause_circle'}
            </span>
            <span className="font-bold text-sm">{config.enabled ? 'Activo' : 'Pausado'}</span>
          </span>
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(e) => onChange('enabled', e.target.checked)}
            className="linux-quick-config__checkbox"
          />
          <span className="linux-quick-config__switch" aria-hidden />
        </label>
      </div>

      <button
        type="button"
        onClick={onSendTest}
        disabled={testing || !config.discord_channel_id}
        className={`linux-quick-config__test-btn py-2.5 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${testFeedback === 'success' ? 'animate-linux-success-flash' : ''} ${testFeedback === 'error' ? 'animate-linux-error-shake' : ''}`}
      >
        <span
          className={`material-symbols-outlined text-[20px] ${testing ? 'animate-linux-sync-spin' : ''}`}
        >
          {testing ? 'progress_activity' : testFeedback === 'success' ? 'check_circle' : 'send'}
        </span>
        <span>
          {testing
            ? 'Disparando refresh...'
            : testFeedback === 'success'
              ? '¡Refresh completado!'
              : 'Disparar refresh manual'}
        </span>
      </button>

      {!config.discord_channel_id && (
        <p className="text-[11px] text-secondary text-center">
          Selecciona un canal de Discord abajo para recibir alertas EOL.
        </p>
      )}
    </div>
  );
}
