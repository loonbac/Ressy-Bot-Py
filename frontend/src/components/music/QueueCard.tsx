import type { MusicQueueResponse } from '@/api/music';
import './QueueCard.css';
import './animations.css';

interface Props {
  queue: MusicQueueResponse | null;
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '--:--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatTotal(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0 min';
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins} min`;
  const hours = Math.floor(mins / 60);
  const rest = mins % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

export default function QueueCard({ queue }: Props) {
  const tracks = queue?.tracks ?? [];

  return (
    <div className="music-queue-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-secondary text-[22px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            queue_music
          </span>
          <span className="font-headline-md text-headline-md text-primary leading-none">
            Cola
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-tertiary">
          <span className="px-2 py-0.5 rounded-full bg-primary-container/30 text-primary font-bold">
            {tracks.length} pistas
          </span>
          <span>·</span>
          <span>{formatTotal(queue?.total_duration_seconds ?? 0)}</span>
        </div>
      </div>

      {tracks.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-tertiary text-sm">
          <span className="material-symbols-outlined text-3xl opacity-50">music_off</span>
          <span>La cola está vacía.</span>
          <span className="text-[11px]">
            Las próximas canciones aparecerán aquí.
          </span>
        </div>
      ) : (
        <div className="music-queue-card__scroll flex-1 min-h-0 overflow-y-auto pr-1 space-y-2">
          {tracks.map((t, idx) => (
            <div
              key={`${t.url}-${idx}`}
              className="music-queue-row flex items-center gap-3 p-2.5 rounded-xl animate-music-track-slide-in"
              style={{ animationDelay: `${idx * 25}ms` }}
            >
              <span className="music-queue-row__index w-7 h-7 rounded-full text-xs font-bold flex items-center justify-center flex-shrink-0">
                {idx + 1}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-on-surface truncate" title={t.title}>
                  {t.title || 'Sin título'}
                </p>
                <p className="text-[11px] text-tertiary truncate">
                  {t.requester_name || 'Anónimo'} · {formatDuration(t.duration_seconds)}
                </p>
              </div>
              {t.thumbnail_url && (
                <img
                  src={t.thumbnail_url}
                  alt=""
                  className="w-10 h-10 rounded-lg object-cover flex-shrink-0"
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
