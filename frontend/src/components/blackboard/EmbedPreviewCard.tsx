import { useState } from 'react';
import type {
  BlackboardAssignment,
  BlackboardConfig,
  BlackboardDiscordRole,
} from '@/api/blackboard';
import './EmbedPreviewCard.css';
import './animations.css';

type Variant = 'new' | 'pending' | 'alert';

const VARIANT_META: Record<Variant, { label: string; icon: string; color: string; title: string }> = {
  new: {
    label: 'Nueva',
    icon: 'fiber_new',
    color: '#8000ff',
    title: '🆕 ¡Nueva Tarea Publicada!',
  },
  pending: {
    label: 'Pendientes',
    icon: 'pending_actions',
    color: '#ff9100',
    title: '📌 Tareas Pendientes',
  },
  alert: {
    label: '24h',
    icon: 'alarm',
    color: '#ff0000',
    title: '⏰ ¡Tarea por Vencer!',
  },
};

interface Props {
  config: BlackboardConfig;
  assignments: BlackboardAssignment[];
  roles: BlackboardDiscordRole[];
  botName?: string;
  botAvatarUrl?: string;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString('es-PE', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function hoursUntil(iso: string | null | undefined): number {
  if (!iso) return 0;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 0;
  return (d.getTime() - Date.now()) / 3600000;
}

function remaining(hours: number): string {
  if (hours <= 0) return 'vencida!';
  if (hours < 1) return `~${Math.round(hours * 60)} min`;
  if (hours < 24) return `~${Math.round(hours)} h`;
  const days = Math.floor(hours / 24);
  const rem = Math.floor(hours % 24);
  return rem > 0 ? `${days}d ${rem}h` : `${days}d`;
}

function urgency(hours: number): string {
  if (hours < 24) return '🔴';
  if (hours < 72) return '🟡';
  return '🟢';
}

const SAMPLE_NEW: BlackboardAssignment = {
  id: -1,
  assignment_id: 'sample-new',
  title: 'Práctica Calificada N°3',
  course_name: 'Programación Web Backend',
  course_id: '',
  due_date: new Date(Date.now() + 36 * 3600 * 1000).toISOString(),
  status: 'Pending',
  source_url: '',
};

const SAMPLE_ALERT: BlackboardAssignment = {
  id: -2,
  assignment_id: 'sample-alert',
  title: 'Laboratorio Final — Docker & K8s',
  course_name: 'DevOps Avanzado',
  course_id: '',
  due_date: new Date(Date.now() + 8 * 3600 * 1000).toISOString(),
  status: 'Pending',
  source_url: '',
};

export default function EmbedPreviewCard({
  config,
  assignments,
  roles,
  botName,
  botAvatarUrl,
}: Props) {
  const [variant, setVariant] = useState<Variant>('pending');
  const meta = VARIANT_META[variant];
  const displayBotName = botName || 'Ressy Bot';

  const role = config.mention_role_id
    ? roles.find((r) => r.id === config.mention_role_id)
    : null;
  const roleColorHex = role
    ? `#${role.color.toString(16).padStart(6, '0')}`
    : '#949cf7';

  const pendingList = assignments
    .filter((a) => {
      const s = (a.status || '').toLowerCase();
      if (s.includes('entreg') || s.includes('done') || s.includes('completed')) return false;
      if (!a.due_date) return true;
      return new Date(a.due_date).getTime() > Date.now();
    })
    .sort((a, b) => (a.due_date || 'z').localeCompare(b.due_date || 'z'))
    .slice(0, 5);

  const now = new Date();
  const time = `${now.getHours().toString().padStart(2, '0')}:${now
    .getMinutes()
    .toString()
    .padStart(2, '0')}`;

  return (
    <div className="bb-embed-preview-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-secondary text-[22px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            visibility
          </span>
          <span className="font-headline-md text-headline-md text-primary leading-none">
            Vista Previa Discord
          </span>
        </div>
        <div className="bb-embed-preview-card__variants rounded-lg p-0.5 flex gap-0.5">
          {(Object.keys(VARIANT_META) as Variant[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setVariant(v)}
              className={
                'bb-embed-preview-card__variant px-2.5 py-1 rounded-md text-[11px] font-bold flex items-center gap-1 ' +
                (variant === v ? 'is-active' : '')
              }
            >
              <span className="material-symbols-outlined text-[14px]">
                {VARIANT_META[v].icon}
              </span>
              {VARIANT_META[v].label}
            </button>
          ))}
        </div>
      </div>

      <div className="bb-embed-preview-card__mock rounded-xl p-3 font-sans shadow-xl flex-1 min-h-0 overflow-y-auto animate-bb-card-enter">
        <div className="flex gap-2">
          <div className="w-9 h-9 rounded-full flex-shrink-0 overflow-hidden bg-secondary flex items-center justify-center">
            {botAvatarUrl ? (
              <img
                src={botAvatarUrl}
                alt={displayBotName}
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="material-symbols-outlined text-white text-[20px]">smart_toy</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-1 flex-wrap">
              <span className="font-bold text-white text-sm hover:underline cursor-pointer">
                {displayBotName}
              </span>
              <span className="bg-[#5865f2] text-[9px] px-1 rounded-sm text-white font-bold uppercase py-0.5">
                BOT
              </span>
              <span className="text-[11px] text-[#949ba4] ml-1">Hoy a las {time}</span>
            </div>

            {role && (
              <div className="text-[13px] mb-1">
                <span
                  className="bb-embed-preview-card__role-pill"
                  style={{
                    background: `${roleColorHex}33`,
                    color: roleColorHex,
                  }}
                >
                  @{role.name}
                </span>
              </div>
            )}

            <div
              className="bb-embed-preview-card__embed key-{variant}"
              style={{ borderLeft: `4px solid ${meta.color}` }}
              key={variant}
            >
              <div className="p-2.5">
                <p className="font-bold text-white text-[13px] leading-tight">{meta.title}</p>
                {variant === 'new' && (
                  <>
                    <div className="text-xs text-[#dbdee1] mt-1.5">
                      Se ha agregado una nueva tarea a tus cursos.
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-2">
                      <div className="bb-embed-preview-card__field">
                        <span className="bb-embed-preview-card__field-name">Tarea</span>
                        <span className="bb-embed-preview-card__field-value">
                          {SAMPLE_NEW.title}
                        </span>
                      </div>
                      <div className="bb-embed-preview-card__field">
                        <span className="bb-embed-preview-card__field-name">
                          Fecha de entrega
                        </span>
                        <span className="bb-embed-preview-card__field-value">
                          {fmtDate(SAMPLE_NEW.due_date)}
                        </span>
                      </div>
                      <div className="bb-embed-preview-card__field">
                        <span className="bb-embed-preview-card__field-name">Curso</span>
                        <span className="bb-embed-preview-card__field-value">
                          {SAMPLE_NEW.course_name}
                        </span>
                      </div>
                    </div>
                  </>
                )}

                {variant === 'pending' && (
                  <>
                    <div className="text-xs text-[#dbdee1] mt-1.5">
                      {pendingList.length === 0 ? (
                        '✅ No hay tareas pendientes ahora mismo.'
                      ) : (
                        <>
                          Tenés <b>{pendingList.length}</b> tarea(s) pendiente(s). ¡A meterle ganas!
                        </>
                      )}
                    </div>
                    {pendingList.map((a) => {
                      const hrs = hoursUntil(a.due_date);
                      return (
                        <div
                          key={a.id}
                          className="mt-2 animate-bb-row-enter"
                        >
                          <p className="text-[11px] font-bold text-white leading-tight">
                            {urgency(hrs)} {a.title}
                            {a.course_name ? ` — ${a.course_name}` : ''}
                          </p>
                          <p className="text-[11px] text-[#dbdee1]">
                            Vence: {fmtDate(a.due_date)} · {remaining(hrs)}
                          </p>
                        </div>
                      );
                    })}
                  </>
                )}

                {variant === 'alert' && (
                  <>
                    <div className="text-xs text-[#dbdee1] mt-1.5">
                      Esta tarea vence en menos de 24 horas.
                    </div>
                    <div className="grid grid-cols-2 gap-2 mt-2">
                      <div className="bb-embed-preview-card__field">
                        <span className="bb-embed-preview-card__field-name">Tarea</span>
                        <span className="bb-embed-preview-card__field-value">
                          {SAMPLE_ALERT.title}
                        </span>
                      </div>
                      <div className="bb-embed-preview-card__field">
                        <span className="bb-embed-preview-card__field-name">
                          Fecha de entrega
                        </span>
                        <span className="bb-embed-preview-card__field-value">
                          {fmtDate(SAMPLE_ALERT.due_date)}
                        </span>
                      </div>
                      <div className="bb-embed-preview-card__field">
                        <span className="bb-embed-preview-card__field-name">
                          Tiempo restante
                        </span>
                        <span className="bb-embed-preview-card__field-value">
                          {remaining(hoursUntil(SAMPLE_ALERT.due_date))}
                        </span>
                      </div>
                      <div className="bb-embed-preview-card__field">
                        <span className="bb-embed-preview-card__field-name">Curso</span>
                        <span className="bb-embed-preview-card__field-value">
                          {SAMPLE_ALERT.course_name}
                        </span>
                      </div>
                    </div>
                  </>
                )}

                <div className="mt-2 text-[10px] text-[#949ba4]">
                  Bot Blackboard · {time}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
