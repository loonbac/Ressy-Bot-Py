import type { LinuxConfig, LinuxDiscordChannel, LinuxRefreshResult } from '@/api/linux';
import './SettingsPanelCard.css';
import './animations.css';

interface ActivityEntry {
  id: string;
  date: string;
  event: string;
  status: 'ok' | 'sent' | 'error';
}

interface Props {
  config: LinuxConfig;
  channels: LinuxDiscordChannel[];
  onChange: <K extends keyof LinuxConfig>(key: K, value: LinuxConfig[K]) => void;
  activity: ActivityEntry[];
  lastRefresh: LinuxRefreshResult | null;
}

const STATUS_META: Record<ActivityEntry['status'], { label: string; cls: string; icon: string }> = {
  ok: { label: 'OK', cls: 'linux-settings__pill--ok', icon: 'check_circle' },
  sent: { label: 'Enviado', cls: 'linux-settings__pill--sent', icon: 'send' },
  error: { label: 'Error', cls: 'linux-settings__pill--error', icon: 'error' },
};

export default function SettingsPanelCard({
  config,
  channels,
  onChange,
  activity,
  lastRefresh,
}: Props) {
  const selectedChannel = channels.find((c) => c.id === config.discord_channel_id) ?? null;

  return (
    <div
      id="linux-settings-panel"
      className="linux-settings rounded-xl p-7 animate-linux-card-enter animate-linux-stagger-4"
    >
      <h3 className="font-headline-md text-headline-md text-primary mb-6 flex items-center gap-2">
        <span className="material-symbols-outlined text-secondary text-[26px]">tune</span>
        Panel de configuración global
      </h3>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-6">
          <div className="flex flex-col gap-2">
            <label className="text-label-sm font-bold text-on-surface-variant uppercase tracking-wider">
              Canal de Discord para alertas
            </label>
            <div className="linux-settings__select-wrap">
              <select
                value={config.discord_channel_id}
                onChange={(e) => onChange('discord_channel_id', e.target.value)}
                className="linux-settings__select"
              >
                <option value="">— Sin canal —</option>
                {channels.map((ch) => (
                  <option key={ch.id} value={ch.id}>
                    {ch.name} · {ch.guild_name}
                  </option>
                ))}
              </select>
              <span className="material-symbols-outlined linux-settings__select-chevron">
                expand_more
              </span>
            </div>
            <p className="text-[11px] text-on-surface-variant">
              {channels.length === 0
                ? 'El bot debe estar conectado para listar canales.'
                : selectedChannel
                  ? `Canal seleccionado: ${selectedChannel.name} · ${selectedChannel.guild_name}`
                  : `${channels.length} canal(es) disponibles. Selecciona uno para recibir alertas EOL.`}
            </p>
            <p className="text-[11px] text-on-surface-variant">
              ID actual:{' '}
              <span className="font-mono text-on-surface">
                {config.discord_channel_id || '— sin canal —'}
              </span>
            </p>
          </div>

          {lastRefresh && (
            <div
              className={`linux-settings__refresh-result rounded-lg p-3 ${lastRefresh.failed > 0 ? 'linux-settings__refresh-result--warn' : 'linux-settings__refresh-result--ok'}`}
            >
              <div className="flex items-center gap-2 text-sm font-bold">
                <span
                  className="material-symbols-outlined text-[18px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  {lastRefresh.failed > 0 ? 'warning' : 'check_circle'}
                </span>
                <span>
                  Último refresh: {lastRefresh.refreshed} ok · {lastRefresh.failed} error
                  {lastRefresh.skipped ? ' · scheduler pausado' : ''}
                </span>
              </div>
              {lastRefresh.errors.length > 0 && (
                <ul className="text-[11px] mt-1 list-disc list-inside opacity-80">
                  {lastRefresh.errors.slice(0, 3).map((err) => (
                    <li key={err.slug}>
                      {err.slug}: {err.error}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="space-y-3">
          <label className="text-label-sm font-bold text-on-surface-variant uppercase tracking-wider">
            Actividad reciente
          </label>
          <div className="linux-settings__activity rounded-xl overflow-hidden">
            <table className="w-full text-left">
              <thead>
                <tr>
                  <th className="px-3 py-2 text-label-sm font-bold text-on-surface-variant">Fecha</th>
                  <th className="px-3 py-2 text-label-sm font-bold text-on-surface-variant">Evento</th>
                  <th className="px-3 py-2 text-label-sm font-bold text-on-surface-variant">Estado</th>
                </tr>
              </thead>
              <tbody>
                {activity.length === 0 && (
                  <tr>
                    <td colSpan={3} className="p-4 text-center text-on-surface-variant text-label-sm">
                      Sin eventos registrados todavía.
                    </td>
                  </tr>
                )}
                {activity.map((row, idx) => {
                  const meta = STATUS_META[row.status];
                  return (
                    <tr
                      key={row.id}
                      className="linux-settings__activity-row animate-linux-row-fade-in"
                      style={{ animationDelay: `${0.04 * idx}s` }}
                    >
                      <td className="px-3 py-2 text-label-sm">{row.date}</td>
                      <td className="px-3 py-2 text-label-sm">{row.event}</td>
                      <td className="px-3 py-2">
                        <span className={`linux-settings__pill ${meta.cls}`}>
                          <span className="material-symbols-outlined text-[14px]">{meta.icon}</span>
                          {meta.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export type { ActivityEntry };
