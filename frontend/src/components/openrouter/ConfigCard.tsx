import { useEffect, useState } from 'react';
import './ConfigCard.css';
import type { OpenRouterConfig, DiscordChannel } from '@/api/openrouter';

interface Props {
  config: OpenRouterConfig | null;
  channels: DiscordChannel[];
  saving?: boolean;
  saveState: 'idle' | 'saving' | 'success' | 'error';
  onSave: (patch: Partial<OpenRouterConfig>) => Promise<void>;
}

export default function ConfigCard({ config, channels, saving, saveState, onSave }: Props) {
  const [aaKey, setAaKey] = useState(config?.aa_api_key ?? '');
  const [githubToken, setGithubToken] = useState(config?.github_token ?? '');
  const [channelId, setChannelId] = useState(config?.discord_channel_id ?? '');
  const [maxModels, setMaxModels] = useState(config?.max_models_command ?? 10);
  const [ttlHours, setTtlHours] = useState(
    Math.round((config?.ttl_seconds ?? 3600) / 3600),
  );
  const [staleDays, setStaleDays] = useState(config?.stale_threshold_days ?? 14);
  const [showAaKey, setShowAaKey] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!config) return;
    setAaKey(config.aa_api_key ?? '');
    setGithubToken(config.github_token ?? '');
    setChannelId(config.discord_channel_id ?? '');
    setMaxModels(config.max_models_command ?? 10);
    setTtlHours(Math.round((config.ttl_seconds ?? 3600) / 3600));
    setStaleDays(config.stale_threshold_days ?? 14);
    setDirty(false);
  }, [config]);

  const markDirty = () => setDirty(true);

  const handleSave = async () => {
    const patch: Partial<OpenRouterConfig> = {
      aa_api_key: aaKey,
      github_token: githubToken,
      discord_channel_id: channelId ?? '',
      max_models_command: maxModels,
      ttl_seconds: Math.max(60, ttlHours * 3600),
      stale_threshold_days: staleDays,
    };
    try {
      await onSave(patch);
      setDirty(false);
    } catch {
      // toast manejado en parent
    }
  };

  const aaKeyConfigured = (config?.aa_api_key ?? '').length > 0;

  return (
    <div className="openrouter-config-card animate-openrouter-card-enter">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-primary text-[22px]">tune</span>
          <div>
            <h3 className="font-display text-headline-md text-primary">
              Configuración rápida
            </h3>
            <p className="text-[11px] text-on-surface-variant">
              Claves API, canal Discord y caché
            </p>
          </div>
        </div>
        <span
          className={`openrouter-config-card__status-pill ${
            aaKeyConfigured
              ? 'openrouter-config-card__status-pill--ok'
              : 'openrouter-config-card__status-pill--missing'
          }`}
        >
          <span className="material-symbols-outlined text-[12px]">
            {aaKeyConfigured ? 'check' : 'warning'}
          </span>
          Clave AA: {aaKeyConfigured ? 'configurada' : 'faltante'}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div className="openrouter-config-card__field">
          <label className="openrouter-config-card__label">
            Clave API · Artificial Analysis
          </label>
          <div className="openrouter-config-card__input-wrap">
            <input
              type={showAaKey ? 'text' : 'password'}
              className="openrouter-config-card__input openrouter-config-card__input--password"
              value={aaKey}
              placeholder="aa-xxxxxxxxxxxxx"
              onChange={(e) => {
                setAaKey(e.target.value);
                markDirty();
              }}
              autoComplete="off"
            />
            <button
              type="button"
              className="openrouter-config-card__eye"
              onClick={() => setShowAaKey((v) => !v)}
              aria-label={showAaKey ? 'Ocultar clave' : 'Mostrar clave'}
            >
              <span className="material-symbols-outlined text-[18px]">
                {showAaKey ? 'visibility_off' : 'visibility'}
              </span>
            </button>
          </div>
          <p className="openrouter-config-card__hint">
            Necesaria para que el scrape de AA traiga benchmarks (ifbench, intelligence_index, τ²).
          </p>
        </div>

        <div className="openrouter-config-card__field">
          <label className="openrouter-config-card__label">
            Token GitHub (opcional)
          </label>
          <div className="openrouter-config-card__input-wrap">
            <input
              type={showToken ? 'text' : 'password'}
              className="openrouter-config-card__input openrouter-config-card__input--password"
              value={githubToken}
              placeholder="ghp_xxxxxxxxxxxxx"
              onChange={(e) => {
                setGithubToken(e.target.value);
                markDirty();
              }}
              autoComplete="off"
            />
            <button
              type="button"
              className="openrouter-config-card__eye"
              onClick={() => setShowToken((v) => !v)}
              aria-label={showToken ? 'Ocultar token' : 'Mostrar token'}
            >
              <span className="material-symbols-outlined text-[18px]">
                {showToken ? 'visibility_off' : 'visibility'}
              </span>
            </button>
          </div>
          <p className="openrouter-config-card__hint">
            Sube el rate limit del scrape BFCL desde 60 a 5000 requests por hora.
          </p>
        </div>

        <div className="openrouter-config-card__field">
          <label className="openrouter-config-card__label">Canal de Discord</label>
          <div className="openrouter-config-card__select-wrap">
            <select
              className="openrouter-config-card__input openrouter-config-card__select"
              value={channelId ?? ''}
              onChange={(e) => {
                setChannelId(e.target.value);
                markDirty();
              }}
            >
              <option value="">— Sin canal —</option>
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.name} · {ch.guild_name}
                </option>
              ))}
            </select>
            <span className="material-symbols-outlined openrouter-config-card__select-chevron">
              expand_more
            </span>
          </div>
          <p className="openrouter-config-card__hint">
            {channels.length === 0
              ? 'El bot debe estar conectado para listar canales. Revisa que esté online.'
              : `Canal donde se publicarán los embeds bi-semanales. ${channels.length} canal(es) disponibles.`}
          </p>
        </div>

        <div className="openrouter-config-card__field">
          <label className="openrouter-config-card__label">
            Modelos en /precios-openrouter (1–25)
          </label>
          <div className="openrouter-config-card__slider-row">
            <input
              type="range"
              min={1}
              max={25}
              value={maxModels}
              onChange={(e) => {
                setMaxModels(Number(e.target.value));
                markDirty();
              }}
              className="openrouter-config-card__slider"
            />
            <span className="openrouter-config-card__slider-value">{maxModels}</span>
          </div>
          <p className="openrouter-config-card__hint">
            Cantidad de modelos mostrados en el comando slash de Discord.
          </p>
        </div>

        <div className="openrouter-config-card__field">
          <label className="openrouter-config-card__label">Cache TTL (horas)</label>
          <div className="openrouter-config-card__slider-row">
            <input
              type="range"
              min={1}
              max={24}
              value={ttlHours}
              onChange={(e) => {
                setTtlHours(Number(e.target.value));
                markDirty();
              }}
              className="openrouter-config-card__slider"
            />
            <span className="openrouter-config-card__slider-value">{ttlHours}h</span>
          </div>
          <p className="openrouter-config-card__hint">
            Tiempo que el catálogo OpenRouter se considera fresco antes de re-fetchear.
          </p>
        </div>

        <div className="openrouter-config-card__field">
          <label className="openrouter-config-card__label">Umbral de scrape viejo (días)</label>
          <div className="openrouter-config-card__slider-row">
            <input
              type="range"
              min={1}
              max={60}
              value={staleDays}
              onChange={(e) => {
                setStaleDays(Number(e.target.value));
                markDirty();
              }}
              className="openrouter-config-card__slider"
            />
            <span className="openrouter-config-card__slider-value">{staleDays}d</span>
          </div>
          <p className="openrouter-config-card__hint">
            Después de este tiempo sin éxito, el scraper se marca como advertencia.
          </p>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          className={`openrouter-config-card__save-btn ${
            saveState === 'success' ? 'animate-openrouter-bloom' : ''
          } ${saveState === 'error' ? 'animate-openrouter-shake' : ''}`}
          onClick={handleSave}
          disabled={!dirty || saving}
        >
          <span
            className={`material-symbols-outlined text-[16px] ${
              saving ? 'animate-openrouter-spin' : ''
            }`}
          >
            {saveState === 'success'
              ? 'check'
              : saveState === 'error'
                ? 'error'
                : saving
                  ? 'progress_activity'
                  : 'save'}
          </span>
          {saving
            ? 'Guardando...'
            : saveState === 'success'
              ? '¡Guardado!'
              : saveState === 'error'
                ? 'Error'
                : dirty
                  ? 'Guardar cambios'
                  : 'Sin cambios'}
        </button>
      </div>
    </div>
  );
}
