import type {
  BlackboardConfig,
  BlackboardDiscordChannel,
  BlackboardDiscordRole,
} from '@/api/blackboard';
import './ScheduleCard.css';
import './animations.css';

interface Props {
  config: BlackboardConfig;
  channels: BlackboardDiscordChannel[];
  roles: BlackboardDiscordRole[];
  onChange: <K extends keyof BlackboardConfig>(key: K, value: BlackboardConfig[K]) => void;
}

const DAYS: Array<{ value: number; label: string }> = [
  { value: 0, label: 'Lunes' },
  { value: 1, label: 'Martes' },
  { value: 2, label: 'Miércoles' },
  { value: 3, label: 'Jueves' },
  { value: 4, label: 'Viernes' },
  { value: 5, label: 'Sábado' },
  { value: 6, label: 'Domingo' },
];

const TIMEZONES = [
  'America/Lima',
  'America/Bogota',
  'America/Buenos_Aires',
  'America/Mexico_City',
  'America/Santiago',
  'Europe/Madrid',
  'UTC',
];

function colorToHex(c: number): string {
  if (!c) return '#99aab5';
  return `#${c.toString(16).padStart(6, '0')}`;
}

export default function ScheduleCard({ config, channels, roles, onChange }: Props) {
  return (
    <div className="bb-schedule-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center gap-2 mb-4 flex-shrink-0">
        <span
          className="material-symbols-outlined text-secondary text-[22px]"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          schedule
        </span>
        <span className="font-headline-md text-headline-md text-primary leading-none">
          Programación
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 flex-1 min-h-0 overflow-y-auto pr-1">
        <div className="col-span-2">
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            Canal Discord
          </label>
          <div className="relative">
            <select
              value={config.discord_channel_id ?? ''}
              onChange={(e) => onChange('discord_channel_id', e.target.value || null)}
              className="bb-schedule-card__select w-full rounded-lg py-2.5 px-3 text-sm appearance-none cursor-pointer pr-9"
            >
              <option value="">Seleccionar canal...</option>
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  {ch.name} — {ch.guild_name}
                </option>
              ))}
            </select>
            <span className="material-symbols-outlined absolute right-2.5 top-1/2 -translate-y-1/2 text-outline pointer-events-none text-[20px]">
              expand_more
            </span>
          </div>
        </div>

        <div className="col-span-2">
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            Mencionar Rol (@Senati)
          </label>
          <div className="relative">
            <select
              value={config.mention_role_id ?? ''}
              onChange={(e) => onChange('mention_role_id', e.target.value || null)}
              className="bb-schedule-card__select w-full rounded-lg py-2.5 px-3 text-sm appearance-none cursor-pointer pr-9"
            >
              <option value="">Sin mención</option>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  @{r.name}
                </option>
              ))}
            </select>
            <span className="material-symbols-outlined absolute right-2.5 top-1/2 -translate-y-1/2 text-outline pointer-events-none text-[20px]">
              alternate_email
            </span>
          </div>
          {config.mention_role_id &&
            (() => {
              const sel = roles.find((r) => r.id === config.mention_role_id);
              if (!sel) return null;
              return (
                <div className="mt-1.5 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-surface-container-low border border-outline-variant/30">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ background: colorToHex(sel.color) }}
                  />
                  <span className="text-[10px] font-mono text-tertiary">@{sel.name}</span>
                </div>
              );
            })()}
        </div>

        <div>
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            Intervalo (min)
          </label>
          <input
            type="number"
            min={10}
            value={config.poll_interval_minutes}
            onChange={(e) => {
              const n = parseInt(e.target.value, 10);
              onChange('poll_interval_minutes', Number.isNaN(n) ? 10 : Math.max(10, n));
            }}
            className="bb-schedule-card__input w-full rounded-lg py-2.5 px-3 text-sm font-body-md"
          />
        </div>

        <div>
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            Resumen Semanal
          </label>
          <div className="relative">
            <select
              value={config.weekly_digest_day}
              onChange={(e) => onChange('weekly_digest_day', parseInt(e.target.value, 10))}
              className="bb-schedule-card__select w-full rounded-lg py-2.5 px-3 text-sm appearance-none cursor-pointer pr-9"
            >
              {DAYS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
            <span className="material-symbols-outlined absolute right-2.5 top-1/2 -translate-y-1/2 text-outline pointer-events-none text-[20px]">
              calendar_today
            </span>
          </div>
        </div>

        <div className="col-span-2">
          <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
            Zona Horaria
          </label>
          <input
            type="text"
            value={config.timezone}
            onChange={(e) => onChange('timezone', e.target.value)}
            placeholder="America/Lima"
            list="bb-tz-list"
            className="bb-schedule-card__input w-full rounded-lg py-2.5 px-3 text-sm font-mono"
          />
          <datalist id="bb-tz-list">
            {TIMEZONES.map((tz) => (
              <option key={tz} value={tz} />
            ))}
          </datalist>
        </div>
      </div>
    </div>
  );
}
