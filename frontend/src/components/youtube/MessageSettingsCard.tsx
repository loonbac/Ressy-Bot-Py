import type { DiscordChannel, YouTubeConfig } from '@/api/youtube';
import EmbedPreview from './EmbedPreview';
import DiscordChannelSelect from './DiscordChannelSelect';

interface Props {
  config: YouTubeConfig;
  discordChannels: DiscordChannel[];
  onMessageChange: (value: string) => void;
  onChannelChange: (id: string | null) => void;
}

export default function MessageSettingsCard({
  config,
  discordChannels,
  onMessageChange,
  onChannelChange,
}: Props) {
  return (
    <div className="bg-primary-fixed/20 backdrop-blur-md rounded-xl p-5 border border-primary-container/30 flex flex-col">
      <h3 className="font-headline-md text-headline-md mb-4 flex items-center gap-2">
        <span
          className="material-symbols-outlined text-secondary text-[20px]"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          forum
        </span>
        Ajustes de Mensaje
      </h3>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col">
          <label className="block text-label-sm text-primary font-bold uppercase mb-1.5">
            Mensaje de anuncio
          </label>
          <textarea
            className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg p-3 text-sm font-body-md min-h-[80px] focus:ring-2 focus:ring-secondary/20 outline-none resize-none transition-all text-on-surface"
            placeholder="@everyone ¡Hay un nuevo video en {canal}!"
            value={config.announcement_message}
            onChange={(e) => onMessageChange(e.target.value)}
          />
          <div className="mt-4">
            <label className="block text-label-sm text-primary font-bold uppercase mb-2">
              Vista Previa
            </label>
            <EmbedPreview announcementMessage={config.announcement_message} />
          </div>
        </div>
        <DiscordChannelSelect
          value={config.discord_channel_id}
          channels={discordChannels}
          onChange={onChannelChange}
        />
      </div>
    </div>
  );
}
