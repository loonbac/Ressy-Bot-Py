import { useState } from 'react';
import { ConfigResponse, BotStatus } from '@/types';

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

  return (
    <section aria-label="Configuration panel" className="relative">
      <div className="relative z-10">
        <div className="mb-12">
          <h2 className="font-headline-lg text-headline-lg text-primary mb-2">
            Panel de Control General
          </h2>
          <p className="text-tertiary font-body-lg">
            Gestiona el comportamiento y la identidad de tu servidor zen.
          </p>
        </div>

        <div className="grid grid-cols-12 gap-8">
          {/* Main Settings List */}
          <div className="col-span-12 lg:col-span-8 bg-surface-container-lowest/60 backdrop-blur-sm border border-white/40 rounded-3xl p-8 shadow-[0px_10px_30px_rgba(168,0,33,0.02)]">
            {configs.length === 0 ? (
              <p className="text-tertiary text-center py-10 italic">
                <span className="sr-only">No configuration values yet</span>
                <span aria-hidden="true">No hay valores de configuración aún</span>
              </p>
            ) : (
              <div className="space-y-10">
                {configs.map((cfg, index) => {
                  const info = getDisplayInfo(cfg.key);
                  const isLast = index === configs.length - 1;
                  const isLoading = loading[cfg.key];
                  const isSuccess = success[cfg.key];
                  const errorMsg = errors[cfg.key];

                  return (
                    <div key={cfg.key} className="group">
                      <div
                        className={
                          'flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 ' +
                          (isLast ? '' : 'border-b border-outline-variant/10')
                        }
                      >
                        <div className="flex-1">
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
                            className="input-zen w-full font-headline-md text-headline-md text-on-surface py-2"
                          />
                          <p className="text-tertiary text-sm mt-2">
                            {info.description}
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          {isSuccess && (
                            <span className="flex items-center gap-1 text-on-secondary-fixed-variant font-label-sm opacity-0 group-hover:opacity-100 transition-opacity" role="status">
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
                            <span className="flex items-center gap-1 text-error font-label-sm" role="alert">
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
                            className="bg-secondary text-on-secondary px-8 py-2.5 rounded-full font-label-sm bloom-btn disabled:opacity-60 disabled:cursor-not-allowed"
                          >
                            {isLoading ? (
                              <>
                                <span className="sr-only">Saving…</span>
                                <span aria-hidden="true">GUARDANDO...</span>
                              </>
                            ) : (
                              <>
                                <span className="sr-only">Save</span>
                                <span aria-hidden="true">GUARDAR</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Side Info Cards */}
          <div className="col-span-12 lg:col-span-4 space-y-8">
            {/* Status Card */}
            <div className="bg-primary-container/30 backdrop-blur-sm border border-primary-fixed/20 rounded-3xl p-6 relative overflow-hidden">
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-headline-md text-primary">
                    Estado del Sistema
                  </h3>
                  <span className={`flex h-3 w-3 rounded-full ${status?.online ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                </div>
                <div className="space-y-4">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-tertiary">Latencia</span>
                    <span className="text-on-surface font-bold">{status ? `${Math.round(status.latency_ms)}ms` : '--ms'}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-tertiary">Activo desde</span>
                    <span className="text-on-surface font-bold">{status ? formatUptime(status.uptime_seconds) : '--'}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-tertiary">Memoria</span>
                    <span className="text-on-surface font-bold">{status ? `${status.memory_mb.toFixed(1)}MB` : '--MB'}</span>
                  </div>
                </div>
              </div>
              <div className="absolute -bottom-4 -right-4 opacity-10">
                <span className="material-symbols-outlined text-[100px]">
                  tsunami
                </span>
              </div>
            </div>

            {/* Help Card */}
            <div className="bg-surface-container-high rounded-3xl p-6 border border-outline-variant/10">
              <h3 className="font-headline-md text-on-surface mb-4">
                ¿Necesitas ayuda?
              </h3>
              <p className="text-tertiary text-sm mb-6">
                Consulta nuestra documentación técnica para ajustes avanzados de
                IA y moderación.
              </p>
              <a
                className="inline-flex items-center gap-2 text-secondary font-bold hover:underline"
                href="#"
              >
                Ir a Documentación
                <span className="material-symbols-outlined text-[18px]">
                  open_in_new
                </span>
              </a>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-20 py-8 border-t border-outline-variant/10 text-center">
          <p className="text-tertiary font-label-sm tracking-widest uppercase">
            Ressy Bot © 2024 — Armonía Digital
          </p>
        </footer>
      </div>
    </section>
  );
}
