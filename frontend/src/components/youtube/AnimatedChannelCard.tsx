import { useRef } from 'react';
import { getProxiedThumbnailUrl } from '@/api/youtube';
import ToggleSwitch from './ToggleSwitch';

interface Props {
  channelId: string;
  channelName: string;
  thumbnailUrl?: string;
  notificationsEnabled: boolean;
  isNew?: boolean;
  isDeleting?: boolean;
  animationDelay?: number;
  onToggle: (enabled: boolean) => void;
  onDelete: () => void;
}

export default function AnimatedChannelCard({
  channelId,
  channelName,
  thumbnailUrl,
  notificationsEnabled,
  isNew = false,
  isDeleting = false,
  animationDelay = 0,
  onToggle,
  onDelete,
}: Props) {
  const rowRef = useRef<HTMLDivElement>(null);

  const handleToggle = (enabled: boolean) => {
    // brief row highlight on toggle
    rowRef.current?.classList.remove('animate-row-highlight');
    void rowRef.current?.offsetWidth; // reflow to restart animation
    rowRef.current?.classList.add('animate-row-highlight');
    onToggle(enabled);
  };

  const animClass = isDeleting
    ? 'animate-card-exit'
    : isNew
      ? 'animate-card-enter-new'
      : 'animate-card-enter';

  return (
    <div
      ref={rowRef}
      style={{ animationDelay: `${animationDelay}ms` }}
      className={`flex items-center justify-between p-3 bg-surface/40 rounded-lg border border-outline-variant/10 hover:shadow-md transition-shadow duration-300 ${animClass}`}
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full border-2 border-secondary/20 overflow-hidden flex-shrink-0">
          {thumbnailUrl ? (
            <img
              src={getProxiedThumbnailUrl(thumbnailUrl)}
              alt={channelName}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full bg-primary-container/30 flex items-center justify-center text-secondary">
              <span className="material-symbols-outlined text-[20px]">smart_display</span>
            </div>
          )}
        </div>
        <div className="min-w-0">
          <h4 className="font-medium text-on-surface text-sm truncate">
            {channelName || channelId}
          </h4>
          <p className="text-label-sm text-on-surface-variant truncate">@{channelId}</p>
        </div>
      </div>

      <div className="flex items-center gap-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-label-sm text-on-surface-variant hidden xl:inline">
            Notificaciones
          </span>
          <ToggleSwitch checked={notificationsEnabled} onChange={handleToggle} />
        </div>
        <button
          onClick={onDelete}
          className="text-outline hover:text-error active:scale-90 transition-all duration-150 p-1"
          aria-label="Eliminar canal"
        >
          <span className="material-symbols-outlined text-[20px]">delete</span>
        </button>
      </div>
    </div>
  );
}
