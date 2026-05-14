import { useCallback, useEffect, useState } from 'react';
import { ConfigResponse, BotStatus } from '@/types';
import { fetchGuilds, updatePresence, type DiscordGuild } from '@/api/config';
import PresenceCard, {
  type PresenceStatus,
  type PresenceActivityType,
} from './config/PresenceCard';

interface ConfigPanelProps {
  configs: ConfigResponse[];
  onUpdate: (key: string, value: unknown) => Promise<void>;
  status?: BotStatus | null;
}

const LABEL_MAP: Record<string, { label: string; description: string; placeholder?: string }> = {
  bot_prefix: {
    label: 'Prefijo de Comando',
    description: 'Símbolo para activar las funciones del bot.',
    placeholder: '/',
  },
  version: {
    label: 'Versión del Bot',
    description: 'Versión actual del sistema.',
  },
};

function getDisplayInfo(key: string) {
  return (
    LABEL_MAP[key] ?? {
      label: key,
      description: 'Configuración del sistema.',
    }
  );
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
}

export default function ConfigPanel({ configs, onUpdate, status }: ConfigPanelProps) {
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState<Record<string, boolean>>({});
  const [guilds, setGuilds] = useState<DiscordGuild[]>([]);
  const [selectedGuildId, setSelectedGuildId] = useState<string>('');
  const [guildsLoading, setGuildsLoading] = useState(true);

  const [selectedStatus, setSelectedStatus] = useState<PresenceStatus>('online');
  const [selectedActivityType, setSelectedActivityType] = useState<PresenceActivityType>('playing');
  const [selectedActivityText, setSelectedActivityText] = useState('');
  const [presenceApplying, setPresenceApplying] = useState(false);
  const [presenceFeedback, setPresenceFeedback] = useState<
    { kind: 'success' | 'error'; text: string } | null
  >(null);

  const loadGuilds = useCallback(async () => {
    try {
      const result = await fetchGuilds();
      setGuilds(result);
    } catch {
      /* ignore */
    } finally {
      setGuildsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGuilds();
  }, [loadGuilds]);

  useEffect(() => {
    const guildCfg = configs.find((c) => c.key === 'guild_id');
    if (guildCfg) setSelectedGuildId(String(guildCfg.value));
  }, [configs]);

  useEffect(() => {
    const statusCfg = configs.find((c) => c.key === 'bot_status');
    if (statusCfg) setSelectedStatus(String(statusCfg.value) as PresenceStatus);
    const typeCfg = configs.find((c) => c.key === 'bot_activity_type');
    if (typeCfg) setSelectedActivityType(String(typeCfg.value) as PresenceActivityType);
    const textCfg = configs.find((c) => c.key === 'bot_activity_text');
    if (textCfg) setSelectedActivityText(String(textCfg.value));
  }, [configs]);

  const handleApplyPresence = async () => {
    setPresenceApplying(true);
    setPresenceFeedback(null);
    try {
      await onUpdate('bot_status', selectedStatus);
      await onUpdate('bot_activity_type', selectedActivityType);
      await onUpdate('bot_activity_text', selectedActivityText);
      await updatePresence();
      setPresenceFeedback({ kind: 'success', text: 'Presencia aplicada' });
      window.setTimeout(() => setPresenceFeedback(null), 4000);
    } catch (err) {
      setPresenceFeedback({
        kind: 'error',
        text: err instanceof Error ? err.message : 'Error',
      });
    } finally {
      setPresenceApplying(false);
    }
  };

  const handleChange = (key: string, raw: string) => {
    setEditing((prev) => ({ ...prev, [key]: raw }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setSuccess((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSave = async (key: string) => {
    setLoading((prev) => ({ ...prev, [key]: true }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setSuccess((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });

    try {
      let parsed: unknown = editing[key];
      try {
        parsed = JSON.parse(parsed as string);
      } catch {
        // keep as string
      }
      await onUpdate(key, parsed);
      setSuccess((prev) => ({ ...prev, [key]: true }));
      setEditing((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } catch (err) {
      setErrors((prev) => ({
        ...prev,
        [key]: err instanceof Error ? err.message : 'Update failed',
      }));
    } finally {
      setLoading((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  const displayValue = (cfg: ConfigResponse) => {
    if (editing[cfg.key] !== undefined) {
      return editing[cfg.key];
    }
    if (typeof cfg.value === 'string') {
      return cfg.value;
    }
    return JSON.stringify(cfg.value);
  };

  const visibleConfigs = configs.filter(
    (cfg) =>
      cfg.key !== 'guild_id' &&
      cfg.key !== 'bot_status' &&
      cfg.key !== 'bot_activity_type' &&
      cfg.key !== 'bot_activity_text',
  );

  return (
    <section
      aria-label="Configuration panel"
      className="h-auto lg:h-[calc(100vh-12rem)] flex flex-col overflow-hidden"
    >
      <div className="mb-5 flex-shrink-0">
        <h2 className="font-headline-lg text-headline-lg text-primary mb-1">
          Panel de Control General
        </h2>
        <p className="text-tertiary font-body-md">
          Gestiona el comportamiento y la identidad de tu servidor zen.
        </p>
      </div>

      <div className="grid grid-cols-12 gap-6 flex-1 min-h-0 overflow-hidden">
        {/* LEFT — Config inputs + Presence */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-4 min-h-0 overflow-y-auto pr-1">
          <div className="bg-surface-container-lowest/60 backdrop-blur-sm border border-outline-variant/20 rounded-2xl p-6 shadow-[0px_10px_30px_rgba(168,0,33,0.02)]">
            <h3 className="font-headline-md text-headline-md text-primary mb-4 flex items-center gap-2">
              <span
                className="material-symbols-outlined text-secondary text-[22px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                tune
              </span>
              Configuración General
            </h3>
            {visibleConfigs.length === 0 ? (
              <p className="text-tertiary text-center py-10 italic">
                No hay valores de configuración aún
              </p>
            ) : (
              <div className="space-y-6">
                {visibleConfigs.map((cfg, index) => {
                  const info = getDisplayInfo(cfg.key);
                  const isLast = index === visibleConfigs.length - 1;
                  const isLoading = loading[cfg.key];
                  const isSuccess = success[cfg.key];
                  const errorMsg = errors[cfg.key];

                  return (
                    <div key={cfg.key} className="group">
                      <div
                        className={
                          'flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-6 ' +
                          (isLast ? '' : 'border-b border-outline-variant/10')
                        }
                      >
                        <div className="flex-1 min-w-0">
                          <label
                            htmlFor={`config-${cfg.key}`}
                            className="block font-label-sm text-secondary uppercase tracking-widest mb-2"
                          >
                            {info.label}
                          </label>
                          <input
                            id={`config-${cfg.key}`}
                            type="text"
                            value={displayValue(cfg)}
                            placeholder={info.placeholder ?? ''}
                            onChange={(e) => handleChange(cfg.key, e.target.value)}
                            disabled={isLoading}
                            aria-label={cfg.key}
                            className="input-zen w-full text-on-surface py-2"
                          />
                          <p className="text-tertiary text-sm mt-2">{info.description}</p>
                        </div>
                        <div className="flex items-center gap-3 flex-shrink-0">
                          {isSuccess && (
                            <span
                              className="flex items-center gap-1 text-on-secondary-fixed-variant font-label-sm opacity-0 group-hover:opacity-100 transition-opacity"
                              role="status"
                            >
                              <span
                                className="material-symbols-outlined text-[14px]"
                                style={{ fontVariationSettings: "'FILL' 1" }}
                              >
                                check_circle
                              </span>
                              Actualizado
                            </span>
                          )}
                          {errorMsg && (
                            <span
                              className="flex items-center gap-1 text-error font-label-sm"
                              role="alert"
                            >
                              <span
                                className="material-symbols-outlined text-[14px]"
                                style={{ fontVariationSettings: "'FILL' 1" }}
                              >
                                error
                              </span>
                              {errorMsg}
                            </span>
                          )}
                          <button
                            onClick={() => handleSave(cfg.key)}
                            disabled={isLoading}
                            className="bg-secondary text-on-secondary px-6 py-2.5 rounded-full font-label-sm bloom-btn disabled:opacity-60 disabled:cursor-not-allowed"
                          >
                            {isLoading ? 'GUARDANDO...' : 'GUARDAR'}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Presence Card */}
          <PresenceCard
            status={selectedStatus}
            activityType={selectedActivityType}
            activityText={selectedActivityText}
            applying={presenceApplying}
            feedback={presenceFeedback}
            botName={status?.bot_name}
            botAvatarUrl={status?.bot_avatar_url}
            onStatusChange={setSelectedStatus}
            onActivityTypeChange={setSelectedActivityType}
            onActivityTextChange={setSelectedActivityText}
            onApply={handleApplyPresence}
          />
        </div>

        {/* RIGHT — Status + Server selection */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-4 min-h-0 overflow-hidden">
          <div className="bg-primary-fixed/20 backdrop-blur-sm border border-primary-container/30 rounded-2xl p-5 relative overflow-hidden flex-shrink-0">
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-headline-md text-primary">Estado del Sistema</h3>
                <span
                  className={`flex h-3 w-3 rounded-full ${
                    status?.online ? 'bg-green-500 animate-pulse' : 'bg-red-500'
                  }`}
                />
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-tertiary">Latencia</span>
                  <span className="text-on-surface font-bold">
                    {status ? `${Math.round(status.latency_ms)}ms` : '--ms'}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-tertiary">Activo desde</span>
                  <span className="text-on-surface font-bold">
                    {status ? formatUptime(status.uptime_seconds) : '--'}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-tertiary">Memoria</span>
                  <span className="text-on-surface font-bold">
                    {status ? `${status.memory_mb.toFixed(1)}MB` : '--MB'}
                  </span>
                </div>
              </div>
            </div>
            <div className="absolute -bottom-4 -right-4 opacity-10">
              <span className="material-symbols-outlined text-[100px]">tsunami</span>
            </div>
          </div>

          <div className="bg-surface-container-lowest/60 backdrop-blur-md rounded-xl p-5 border border-outline-variant/20 shadow-sm flex flex-col flex-1 min-h-0">
            <h3 className="font-display text-headline-md mb-4 flex items-center gap-3 flex-shrink-0">
              <span className="material-symbols-outlined text-secondary">dns</span>
              Servidor Activo
            </h3>

            {guilds.length > 0 ? (
              <>
                <div className="flex-1 overflow-y-auto min-h-0 space-y-2">
                  {guilds.map((g) => {
                    const isSelected = selectedGuildId === g.id;
                    return (
                      <button
                        key={g.id}
                        onClick={() => {
                          setSelectedGuildId(g.id);
                          onUpdate('guild_id', g.id);
                        }}
                        className={`w-full flex items-center gap-3 p-3 rounded-xl border-2 transition-all duration-300 text-left ${
                          isSelected
                            ? 'border-secondary bg-secondary/5 shadow-[0px_4px_15px_rgba(183,19,41,0.1)]'
                            : 'border-outline-variant/20 hover:border-outline-variant/50 bg-surface/40'
                        }`}
                      >
                        <div className="w-10 h-10 rounded-full overflow-hidden flex-shrink-0 bg-primary-container/30 border border-outline-variant/20">
                          {g.icon_url ? (
                            <img
                              src={g.icon_url}
                              alt={g.name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <span className="material-symbols-outlined text-primary text-[18px]">
                                tag
                              </span>
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-on-surface truncate text-sm">{g.name}</p>
                          <p className="text-label-sm text-tertiary">
                            {g.member_count} miembros
                          </p>
                        </div>
                        {isSelected && (
                          <span className="material-symbols-outlined text-secondary text-[20px]">
                            check_circle
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
                <p className="text-tertiary text-xs mt-3 text-center flex-shrink-0">
                  Los selectores de canal solo mostrarán canales de este servidor.
                </p>
              </>
            ) : guildsLoading ? (
              <p className="text-tertiary text-sm text-center py-4">Cargando servidores...</p>
            ) : (
              <p className="text-tertiary text-sm text-center py-4">
                No hay servidores disponibles
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
