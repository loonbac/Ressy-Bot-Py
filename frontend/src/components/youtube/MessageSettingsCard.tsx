import type { DiscordChannel, YouTubeConfig } from '@/api/youtube';
import EmbedPreview from './EmbedPreview';
import DiscordChannelSelect from './DiscordChannelSelect';

interface Props {
  config: YouTubeConfig;
  discordChannels: DiscordChannel[];
  botName?: string;
  botAvatarUrl?: string;
  onMessageChange: (value: string) => void;
  onChannelChange: (id: string | null) => void;
}

export default function MessageSettingsCard({
  config,
  discordChannels,
  botName,
  botAvatarUrl,
  onMessageChange,
  onChannelChange,
}: Props) {
  return (
    <div className="bg-primary-fixed/20 backdrop-blur-md rounded-xl p-5 border border-primary-container/30 flex flex-col flex-1 min-h-0">
      <h3 className="font-headline-md text-headline-md mb-3 flex items-center gap-2 flex-shrink-0">
        <span
          className="material-symbols-outlined text-secondary text-[20px]"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          forum
        </span>
        Ajustes de Mensaje
      </h3>
      <div className="flex flex-col gap-3 flex-1 min-h-0 overflow-y-auto pr-1">
        <div className="flex flex-col flex-shrink-0">
          <label className="block text-label-sm text-primary font-bold uppercase mb-1.5">
            Mensaje de anuncio
          </label>
          <textarea
            className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg p-3 text-sm font-body-md min-h-[64px] focus:ring-2 focus:ring-secondary/20 outline-none resize-none transition-all text-on-surface"
            placeholder="@everyone ¡Hay un nuevo video en {canal}!"
            value={config.announcement_message}
            onChange={(e) => onMessageChange(e.target.value)}
          />
        </div>
        <div className="flex-shrink-0">
          <label className="block text-label-sm text-primary font-bold uppercase mb-1.5">
            Vista Previa
          </label>
          <EmbedPreview
            announcementMessage={config.announcement_message}
            botName={botName}
            botAvatarUrl={botAvatarUrl}
          />
        </div>
        <div className="flex-shrink-0">
          <DiscordChannelSelect
            value={config.discord_channel_id}
            channels={discordChannels}
            onChange={onChannelChange}
          />
        </div>
      </div>
    </div>
  );
}
