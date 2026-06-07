import type { VideoManagerStatus } from '@/api/videos';
import './base.css';

interface Props {
  status: VideoManagerStatus | null;
  workerCount: number;
}

export default function StatusCard({ status, workerCount }: Props) {
  const online = Boolean(status?.online);
  const max = status?.max_workers ?? 5;
  const busy = status?.busy ?? 0;
  const idle = status?.idle ?? 0;

  return (
    <div className="videos-card p-4 h-full flex flex-col gap-3 animate-videos-card-enter animate-videos-stagger-1">
      <span className="videos-card__accent" />
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-[20px]"
            style={{ color: '#ff0050', fontVariationSettings: "'FILL' 1" }}
          >
            smart_display
          </span>
          <h3 className="font-headline-md text-on-surface text-base">Worker-manager</h3>
        </div>
        <span
          className={
            'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ' +
            (online
              ? 'text-green-600 bg-green-500/10'
              : 'text-gray-500 bg-gray-500/10')
          }
        >
          <span
            className={
              'videos-dot ' + (online ? 'videos-dot--idle animate-videos-pulse-ring' : 'videos-dot--offline')
            }
          />
          {online ? 'En línea' : 'Sin conexión'}
        </span>
      </div>

      {online ? (
        <div className="grid grid-cols-3 gap-2 mt-1">
          <Stat label="Workers" value={`${workerCount}/${max}`} />
          <Stat label="Libres" value={String(idle)} />
          <Stat label="En vivo" value={String(busy)} accent={busy > 0} />
        </div>
      ) : (
        <p className="text-sm text-on-surface-variant">
          {status?.detail ||
            'El servicio de videos no responde. Verifica que el contenedor video-worker esté arriba.'}
        </p>
      )}

      {status?.quality && (
        <p className="text-xs text-on-surface-variant mt-auto">
          Calidad: {status.quality.width}×{status.quality.height} · {status.quality.fps}fps ·{' '}
          {status.quality.bitrate}kbps
        </p>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-lg bg-surface-container-low/60 border border-outline-variant/40 px-2 py-2 text-center">
      <div
        className="font-headline-md text-lg"
        style={{ color: accent ? '#ff0050' : 'var(--color-on-surface)' }}
      >
        {value}
      </div>
      <div className="text-[0.65rem] uppercase tracking-wide text-on-surface-variant">{label}</div>
    </div>
  );
}
