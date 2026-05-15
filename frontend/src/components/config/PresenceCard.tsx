import { useState } from 'react';
import './PresenceCard.css';

export type PresenceStatus = 'online' | 'idle' | 'dnd' | 'invisible';
export type PresenceActivityType = 'playing' | 'watching' | 'listening' | 'competing' | 'custom';

interface Props {
  status: PresenceStatus;
  activityType: PresenceActivityType;
  activityText: string;
  applying: boolean;
  feedback: { kind: 'success' | 'error'; text: string } | null;
  botName?: string;
  botAvatarUrl?: string;
  onStatusChange: (s: PresenceStatus) => void;
  onActivityTypeChange: (t: PresenceActivityType) => void;
  onActivityTextChange: (t: string) => void;
  onApply: () => void;
}

const STATUS_OPTIONS: Array<{
  id: PresenceStatus;
  label: string;
  icon: string;
}> = [
  { id: 'online', label: 'En línea', icon: 'check_circle' },
  { id: 'idle', label: 'Ausente', icon: 'schedule' },
  { id: 'dnd', label: 'No molestar', icon: 'do_not_disturb_on' },
  { id: 'invisible', label: 'Invisible', icon: 'visibility_off' },
];

const ACTIVITY_OPTIONS: Array<{
  id: PresenceActivityType;
  label: string;
  icon: string;
  prefix: string;
}> = [
  { id: 'custom', label: 'Personalizado', icon: 'chat', prefix: '' },
  { id: 'playing', label: 'Jugando', icon: 'sports_esports', prefix: 'Jugando' },
  { id: 'watching', label: 'Viendo', icon: 'visibility', prefix: 'Viendo' },
  { id: 'listening', label: 'Escuchando', icon: 'headphones', prefix: 'Escuchando' },
  { id: 'competing', label: 'Compitiendo', icon: 'emoji_events', prefix: 'Compitiendo en' },
];

export default function PresenceCard({
  status,
  activityType,
  activityText,
  applying,
  feedback,
  botName,
  botAvatarUrl,
  onStatusChange,
  onActivityTypeChange,
  onActivityTextChange,
  onApply,
}: Props) {
  const [poppedKey, setPoppedKey] = useState<string | null>(null);

  const pop = (key: string) => {
    setPoppedKey(key);
    window.setTimeout(() => setPoppedKey(null), 320);
  };

  const activityPreview = (() => {
    const opt = ACTIVITY_OPTIONS.find((o) => o.id === activityType);
    const txt = activityText.trim();
    if (!opt || !txt) return null;
    return `${opt.prefix} ${txt}`;
  })();

  return (
    <div className="presence-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)]">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-secondary text-[22px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            smart_toy
          </span>
          <span className="font-headline-md text-headline-md text-primary leading-none">
            Presencia del Bot
          </span>
        </div>
        {feedback && (
          <span
            className={
              'presence-card__feedback ' +
              (feedback.kind === 'success' ? 'is-success' : 'is-error')
            }
          >
            <span
              className="material-symbols-outlined text-[16px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              {feedback.kind === 'success' ? 'check_circle' : 'error'}
            </span>
            {feedback.text}
          </span>
        )}
      </div>

      {/* Live preview */}
      <div className="presence-card__preview mb-4">
        <div className="presence-card__preview-avatar">
          {botAvatarUrl ? (
            <img src={botAvatarUrl} alt={botName || 'Bot'} />
          ) : (
            <span
              className="material-symbols-outlined absolute inset-0 m-auto w-fit h-fit text-white"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              smart_toy
            </span>
          )}
          {status !== 'invisible' && (
            <span className={`presence-card__preview-dot ${status}`} />
          )}
          {status === 'invisible' && <span className="presence-card__preview-dot invisible" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="presence-card__preview-name truncate">{botName || 'Ressy Bot'}</p>
          {activityPreview ? (
            <p className="presence-card__preview-activity truncate">{activityPreview}</p>
          ) : (
            <p className="presence-card__preview-activity italic opacity-60">
              Sin actividad configurada
            </p>
          )}
        </div>
      </div>

      {/* Status pills */}
      <div className="mb-4">
        <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-2">
          Estado
        </label>
        <div className="presence-card__pills">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => {
                onStatusChange(opt.id);
                pop(`s-${opt.id}`);
              }}
              className={
                'presence-card__pill ' +
                (status === opt.id ? 'is-active ' : '') +
                (poppedKey === `s-${opt.id}` ? 'is-just-picked' : '')
              }
            >
              <span className={`presence-card__pill-icon ${opt.id}`}>
                <span
                  className="material-symbols-outlined text-[18px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  {opt.icon}
                </span>
              </span>
              <span className="presence-card__pill-label">{opt.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Activity pills */}
      <div className="mb-4">
        <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-2">
          Tipo de Actividad
        </label>
        <div className="presence-card__pills">
          {ACTIVITY_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => {
                onActivityTypeChange(opt.id);
                pop(`a-${opt.id}`);
              }}
              className={
                'presence-card__pill ' +
                (activityType === opt.id ? 'is-active ' : '') +
                (poppedKey === `a-${opt.id}` ? 'is-just-picked' : '')
              }
            >
              <span className={`presence-card__pill-icon ${opt.id}`}>
                <span
                  className="material-symbols-outlined text-[18px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  {opt.icon}
                </span>
              </span>
              <span className="presence-card__pill-label">{opt.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Activity text */}
      <div className="mb-4">
        <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-2">
          Texto
        </label>
        <input
          type="text"
          value={activityText}
          onChange={(e) => onActivityTextChange(e.target.value)}
          placeholder="con el santuario digital"
          className="presence-card__input w-full rounded-lg py-2.5 px-3 text-sm font-body-md"
        />
      </div>

      <button
        type="button"
        onClick={onApply}
        disabled={applying}
        className="presence-card__apply w-full py-2.5 rounded-xl text-sm font-bold flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed bloom-btn"
      >
        <span
          className={`material-symbols-outlined text-[18px] ${applying ? 'animate-spin' : ''}`}
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          {applying ? 'progress_activity' : 'check'}
        </span>
        {applying ? 'Aplicando...' : 'Aplicar Presencia'}
      </button>
    </div>
  );
}
