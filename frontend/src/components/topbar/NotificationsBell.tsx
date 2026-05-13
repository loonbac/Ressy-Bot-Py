import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchActivity, type ActivityEvent } from '@/api/activity';
import './NotificationsBell.css';

const KIND_ICONS: Record<ActivityEvent['kind'], string> = {
  welcome: 'waving_hand',
  blackboard: 'school',
  youtube: 'smart_display',
  scrape: 'precision_manufacturing',
  config: 'settings',
  system: 'info',
};

function timeAgo(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '';
  const diffMs = Date.now() - t;
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} min`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} h`;
  const d = Math.floor(hr / 24);
  return `${d} d`;
}

export default function NotificationsBell() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [open, setOpen] = useState(false);
  const [unseenCount, setUnseenCount] = useState(0);
  const [ringing, setRinging] = useState(false);
  const lastSeenIdRef = useRef<number>(0);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    try {
      const items = await fetchActivity(30);
      setEvents(items);
      const top = items[0]?.id ?? 0;
      if (top > lastSeenIdRef.current && !open) {
        const newCount = items.filter((e) => e.id > lastSeenIdRef.current).length;
        setUnseenCount(newCount);
        if (newCount > 0) {
          setRinging(true);
          window.setTimeout(() => setRinging(false), 700);
        }
      }
    } catch {
      /* ignore */
    }
  }, [open]);

  useEffect(() => {
    load();
    const interval = window.setInterval(load, 10000);
    return () => window.clearInterval(interval);
  }, [load]);

  useEffect(() => {
    if (open && events.length > 0) {
      lastSeenIdRef.current = events[0].id;
      setUnseenCount(0);
    }
  }, [open, events]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        aria-label="Notificaciones"
        onClick={() => setOpen((v) => !v)}
        className={`topbar-bell ${ringing ? 'is-ringing' : ''}`}
      >
        <span className="material-symbols-outlined">notifications</span>
        {unseenCount > 0 && (
          <span className="topbar-bell__badge">{unseenCount > 99 ? '99+' : unseenCount}</span>
        )}
      </button>

      {open && (
        <div className="topbar-bell__panel">
          <div className="topbar-bell__header">
            <div className="flex items-center gap-2">
              <span
                className="material-symbols-outlined text-secondary"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                history
              </span>
              <span className="font-headline-md text-base text-primary">Actividad</span>
              <span className="text-label-sm text-tertiary bg-surface-container-highest px-2 py-0.5 rounded-full">
                {events.length}
              </span>
            </div>
            <button
              type="button"
              onClick={load}
              className="text-tertiary hover:text-secondary transition-colors"
              title="Refrescar"
            >
              <span className="material-symbols-outlined text-[18px]">refresh</span>
            </button>
          </div>

          <div className="topbar-bell__list">
            {events.length === 0 ? (
              <div className="topbar-bell__empty">
                <span className="material-symbols-outlined text-3xl block mb-2 opacity-40">
                  hourglass_empty
                </span>
                <p className="text-sm">Sin actividad reciente todavía</p>
              </div>
            ) : (
              events.map((e) => (
                <div key={e.id} className="topbar-bell__item">
                  <div className={`topbar-bell__item-icon ${e.kind}`}>
                    <span className="material-symbols-outlined text-[18px]">
                      {KIND_ICONS[e.kind] || 'info'}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="topbar-bell__item-title">{e.title}</p>
                    {e.detail && <p className="topbar-bell__item-detail">{e.detail}</p>}
                    <p className="topbar-bell__item-time">hace {timeAgo(e.ts)}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
