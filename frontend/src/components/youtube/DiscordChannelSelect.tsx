import type { DiscordChannel } from '@/api/youtube';

interface Props {
  value: string | null;
  channels: DiscordChannel[];
  onChange: (id: string | null) => void;
}

export default function DiscordChannelSelect({ value, channels, onChange }: Props) {
  return (
    <div>
      <label className="block text-label-sm text-primary font-bold uppercase mb-1.5">
        Canal de Discord
      </label>
      <div className="relative">
        <select
          className="w-full appearance-none bg-surface-container-low border border-outline-variant/30 rounded-lg p-3 text-sm font-body-md focus:ring-2 focus:ring-secondary/20 outline-none cursor-pointer text-on-surface"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value ? e.target.value : null)}
        >
          <option value="">Seleccionar canal...</option>
          {channels.map((ch) => (
            <option key={ch.id} value={ch.id}>
              {ch.name} — {ch.guild_name}
            </option>
          ))}
        </select>
        <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-[18px]">
          expand_more
        </span>
      </div>
    </div>
  );
}
