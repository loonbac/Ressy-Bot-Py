import './SecurityCard.css';
import type { CodeRunnerConfig, CodeRunnerDiscordRole } from '@/api/code-runner';
import type { MinimaxModel } from '@/api/ai-chat';

interface Props {
  config: CodeRunnerConfig;
  models: MinimaxModel[];
  modelsLoading: boolean;
  roles: CodeRunnerDiscordRole[];
  onPatch: (patch: Partial<CodeRunnerConfig>) => void;
}

export default function SecurityCard({ config, models, modelsLoading, roles, onPatch }: Props) {
  const knownModel = models.some((m) => m.id === config.security_model);
  const selected = new Set(config.mod_role_names.map((r) => r.toLowerCase()));

  const toggleRole = (name: string) => {
    const lower = name.toLowerCase();
    const next = config.mod_role_names.filter((r) => r.toLowerCase() !== lower);
    if (!selected.has(lower)) next.push(name);
    onPatch({ mod_role_names: next });
  };

  // Roles configurados que ya no existen en el servidor (o bot offline).
  const orphanRoles = config.mod_role_names.filter(
    (r) => !roles.some((role) => role.name.toLowerCase() === r.toLowerCase()),
  );

  return (
    <div className="cr-card cr-card--accent cr-security-card animate-cr-card-enter animate-cr-stagger-4 w-full flex flex-col">
      <div className="flex items-center gap-3 mb-5">
        <span className="cr-card__icon material-symbols-outlined">shield_person</span>
        <div>
          <h3 className="font-headline-md text-headline-md text-primary">Seguridad</h3>
          <p className="text-[11px] text-on-surface-variant">
            Análisis pre-ejecución vía MiniMax + reglas locales fail-closed.
          </p>
        </div>
      </div>

      <div className="space-y-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-medium">Análisis de seguridad activo</p>
            <p className="text-[11px] text-on-surface-variant">
              Escaneo heurístico + LLM antes de ejecutar.
            </p>
          </div>
          <label className="cr-toggle-row">
            <span className={`cr-toggle ${config.security_enabled ? 'cr-toggle--on' : ''}`}>
              <input
                type="checkbox"
                className="sr-only"
                checked={config.security_enabled}
                onChange={(e) => onPatch({ security_enabled: e.target.checked })}
              />
              <span className="cr-toggle__thumb" />
            </span>
          </label>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="cr-label">
              Modelo de seguridad
              {modelsLoading && <span className="ml-2 opacity-60">cargando...</span>}
            </label>
            <div className="cr-select-wrap">
              <select
                className="cr-input cr-select"
                value={config.security_model}
                onChange={(e) => onPatch({ security_model: e.target.value })}
                disabled={modelsLoading && models.length === 0}
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
                {!knownModel && config.security_model && (
                  <option value={config.security_model}>{config.security_model} · personalizado</option>
                )}
              </select>
              <span className="material-symbols-outlined cr-select__chevron">expand_more</span>
            </div>
            <p className="cr-hint">
              Mismo catálogo MiniMax que Chat IA. Recomendado: <code>MiniMax-M2.7</code> para análisis riguroso.
            </p>
          </div>

          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="cr-label">Máx. infracciones por usuario</label>
              <span className="cr-slider-value">{config.max_infractions}</span>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              value={config.max_infractions}
              onChange={(e) => onPatch({ max_infractions: Number(e.target.value) })}
              className="cr-slider"
            />
            <p className="cr-hint">A partir de este número, cada cooldown se multiplica por las infracciones excedentes.</p>
          </div>
        </div>

        <div>
          <label className="cr-label">Roles moderadores</label>
          {roles.length === 0 ? (
            <p className="cr-hint">
              No se pudieron listar roles. El bot debe estar online y conectado al servidor configurado en
              <code> guild_id</code>.
            </p>
          ) : (
            <>
              <p className="cr-hint !mt-0 mb-2">
                Selecciona los roles que pueden leer y escribir en los canales de sesión. Click para activar/desactivar.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {roles.map((role, idx) => {
                  const active = selected.has(role.name.toLowerCase());
                  return (
                    <button
                      key={role.id}
                      type="button"
                      onClick={() => toggleRole(role.name)}
                      className={`cr-chip ${active ? 'cr-chip--active' : 'cr-chip--inactive'} animate-cr-chip-pop`}
                      style={{ animationDelay: `${idx * 30}ms` }}
                      title={role.guild_name}
                    >
                      {active && <span className="material-symbols-outlined text-[12px]">check</span>}
                      @{role.name}
                    </button>
                  );
                })}
              </div>
            </>
          )}
          {orphanRoles.length > 0 && (
            <div className="mt-2">
              <p className="cr-hint !mt-0">
                Roles guardados que ya no existen en el servidor (se mantienen hasta que guardes):
              </p>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {orphanRoles.map((r, idx) => (
                  <button
                    key={`orphan-${r}-${idx}`}
                    type="button"
                    onClick={() => toggleRole(r)}
                    className="cr-chip cr-chip--inactive"
                    title="Click para quitar"
                  >
                    @{r} ✕
                  </button>
                ))}
              </div>
            </div>
          )}
          {config.mod_role_names.length === 0 && roles.length > 0 && (
            <p className="cr-hint">
              Sin roles seleccionados — solo el creador de la sesión podrá escribir en su canal.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
