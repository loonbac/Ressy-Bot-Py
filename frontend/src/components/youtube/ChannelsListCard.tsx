import type { YouTubeSubscription, YouTubeSearchResult } from '@/api/youtube';
import AnimatedChannelCard from './AnimatedChannelCard';
import AddChannelSearch from './AddChannelSearch';

interface Props {
  subscriptions: YouTubeSubscription[];
  newChannelId: string | null;
  deletingIds: Set<string>;
  onToggleNotifications: (channelId: string, enabled: boolean) => void;
  onDeleteChannel: (channelId: string) => void;
  onAddChannel: (result: YouTubeSearchResult) => Promise<void> | void;
}

export default function ChannelsListCard({
  subscriptions,
  newChannelId,
  deletingIds,
  onToggleNotifications,
  onDeleteChannel,
  onAddChannel,
}: Props) {
  return (
    <section className="relative z-20 bg-surface-container-lowest/60 backdrop-blur-md rounded-xl border border-white/40 shadow-sm flex flex-col flex-1 min-h-0">
      <div className="flex items-center justify-between px-6 pt-4 pb-3 border-b border-outline-variant/10 flex-shrink-0">
        <h3 className="font-headline-md text-headline-md flex items-center gap-2">
          <span className="material-symbols-outlined text-secondary text-[22px]">subscriptions</span>
          Canales Sincronizados
        </h3>
        <span className="bg-primary-fixed/30 text-on-primary-fixed-variant px-3 py-0.5 rounded-full text-label-sm">
          {subscriptions.length}
        </span>
      </div>

      <div className="px-6 py-3 flex-1 min-h-0 overflow-y-auto">
        {subscriptions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <span className="material-symbols-outlined text-4xl text-outline-variant mb-3">
              subscriptions
            </span>
            <p className="text-on-surface-variant font-body-md text-sm">
              No hay canales sincronizados
            </p>
            <p className="text-tertiary text-xs mt-1">
              Añade un canal para comenzar a recibir notificaciones
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {subscriptions.map((sub, index) => (
              <AnimatedChannelCard
                key={sub.channel_id}
                channelId={sub.channel_id}
                channelName={sub.channel_name}
                thumbnailUrl={sub.thumbnail_url}
                notificationsEnabled={sub.notifications_enabled}
                pendingHubSubscribe={sub.pending_hub_subscribe === 1}
                isNew={sub.channel_id === newChannelId}
                isDeleting={deletingIds.has(sub.channel_id)}
                animationDelay={index * 55}
                onToggle={(enabled) => onToggleNotifications(sub.channel_id, enabled)}
                onDelete={() => onDeleteChannel(sub.channel_id)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="px-6 py-3 border-t border-outline-variant/15 flex-shrink-0">
        <AddChannelSearch onSelect={onAddChannel} />
      </div>
    </section>
  );
}
