import './GeneralStatusCard.css';
import type { CodeRunnerConfig, CodeRunnerDiscordChannel } from '@/api/code-runner';

interface Props {
  config: CodeRunnerConfig;
  channels: CodeRunnerDiscordChannel[];
  republishing?: boolean;
  onPatch: (patch: Partial<CodeRunnerConfig>) => void;
  onRepublish: () => void;
}

export default function GeneralStatusCard({ config, channels, republishing, onPatch, onRepublish }: Props) {
  const lobbyConfigured = Boolean(config.trigger_channel_id);
  const lobbyPublished = Boolean(config.lobby_message_id);

  return (
    <div className="cr-card cr-general-card animate-cr-card-enter animate-cr-stagger-1 w-full flex flex-col">
      <div className="flex items-center gap-3 mb-6">
        <span className="cr-card__icon material-symbols-outlined">hub</span>
        <div>
          <h3 className="font-headline-md text-headline-md text-primary">Estado General</h3>
          <p className="text-[11px] text-on-surface-variant">
            Lobby de creación de sesiones, categoría destino y tiempos.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-5">
        <div>
          <label className="cr-label">Canal de Lobby / Trigger</label>
          <div className="cr-select-wrap">
            <select
              className="cr-input cr-select"
              value={config.trigger_channel_id ?? ''}
              onChange={(e) => onPatch({ trigger_channel_id: e.target.value || null })}
            >
              <option value="">— Sin canal asignado —</option>
              {channels.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} · {c.guild_name}
                </option>
              ))}
            </select>
            <span className="material-symbols-outlined cr-select__chevron">expand_more</span>
          </div>
          <p className="cr-hint">
            {channels.length === 0
              ? 'Bot offline o sin canales. Conéctalo para listar canales.'
              : `${channels.length} canal(es) disponibles. Aquí se publica el botón "Crear sesión".`}
          </p>
        </div>

        <div>
          <label className="cr-label">Categoría de destino (Discord ID)</label>
          <input
            type="text"
            className="cr-input"
            placeholder="982645138281234567"
            value={config.category_id ?? ''}
            onChange={(e) => onPatch({ category_id: e.target.value || null })}
            spellCheck={false}
          />
          <p className="cr-hint">Categoría donde se crean los canales temporales. Vacío = sin categoría.</p>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="cr-label">Tiempo de espera de sesión (min)</label>
            <span className="cr-slider-value">{config.session_timeout_minutes}m</span>
          </div>
          <input
            type="range"
            min={1}
            max={180}
            value={config.session_timeout_minutes}
            onChange={(e) => onPatch({ session_timeout_minutes: Number(e.target.value) })}
            className="cr-slider"
          />
          <p className="cr-hint">Tras este tiempo sin actividad, el reaper cierra el canal y archiva el transcript.</p>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="cr-label">Cooldown entre creaciones (s)</label>
            <span className="cr-slider-value">{config.cooldown_seconds}s</span>
          </div>
          <input
            type="range"
            min={1}
            max={600}
            value={config.cooldown_seconds}
            onChange={(e) => onPatch({ cooldown_seconds: Number(e.target.value) })}
            className="cr-slider"
          />
          <p className="cr-hint">Tiempo mínimo entre dos creaciones de sesión por el mismo usuario.</p>
        </div>
      </div>

      <div className="cr-general-card__footer mt-auto">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="cr-label !mb-0">Lobby</span>
          {!lobbyConfigured ? (
            <span className="cr-status-pill cr-status-pill--warn">Sin canal</span>
          ) : lobbyPublished ? (
            <span className="cr-status-pill cr-status-pill--ok">Publicado · ID {config.lobby_message_id?.slice(-6)}</span>
          ) : (
            <span className="cr-status-pill cr-status-pill--warn">Canal listo, sin publicar</span>
          )}
        </div>
        <button
          type="button"
          onClick={onRepublish}
          disabled={!lobbyConfigured || republishing}
          className="cr-secondary-btn"
        >
          <span className={`material-symbols-outlined text-[16px] ${republishing ? 'animate-cr-spin' : ''}`}>
            {republishing ? 'progress_activity' : 'refresh'}
          </span>
          {republishing ? 'Republicando...' : 'Republicar lobby'}
        </button>
      </div>
    </div>
  );
}
