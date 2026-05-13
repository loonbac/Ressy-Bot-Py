interface Props {
  announcementMessage: string;
  botName?: string;
  botAvatarUrl?: string;
}

const SAMPLE_CHANNEL = 'Canal de Ejemplo';
const SAMPLE_VIDEO_TITLE = 'Título del Nuevo Video';
const SAMPLE_VIDEO_DESC = 'Nuevo video publicado en YouTube';
const SAMPLE_THUMBNAIL = 'https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg';
const YOUTUBE_RED = '#ff0000';

function renderContent(template: string) {
  if (!template) return null;
  const parts = template.split(/(\{canal\}|@everyone|@here)/g);
  return parts.map((part, idx) => {
    if (part === '{canal}') {
      return <span key={idx}>{SAMPLE_CHANNEL}</span>;
    }
    if (part === '@everyone' || part === '@here') {
      return (
        <span
          key={idx}
          className="text-[#949cf7] bg-[#3c4270] rounded px-0.5 hover:bg-[#5865f2] hover:text-white cursor-pointer transition-colors"
        >
          {part}
        </span>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}

export default function EmbedPreview({ announcementMessage, botName, botAvatarUrl }: Props) {
  const now = new Date();
  const time = `${now.getHours().toString().padStart(2, '0')}:${now
    .getMinutes()
    .toString()
    .padStart(2, '0')}`;
  const displayBotName = botName || 'Ressy Bot';
  const content = renderContent(announcementMessage);

  return (
    <div className="bg-[#313338] rounded-xl p-4 text-[#dbdee1] font-sans shadow-xl">
      <div className="flex gap-3">
        <div className="w-10 h-10 rounded-full flex-shrink-0 overflow-hidden bg-secondary flex items-center justify-center">
          {botAvatarUrl ? (
            <img src={botAvatarUrl} alt={displayBotName} className="w-full h-full object-cover" />
          ) : (
            <span className="material-symbols-outlined text-white">smart_toy</span>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-bold text-white hover:underline cursor-pointer">
              {displayBotName}
            </span>
            <span className="bg-[#5865f2] text-[10px] px-1 rounded-sm text-white font-bold uppercase py-0.5">
              BOT
            </span>
            <span className="text-xs text-[#949ba4] ml-1">Hoy a las {time}</span>
          </div>

          {content && (
            <div className="text-sm leading-relaxed mb-2 break-words whitespace-pre-line">
              {content}
            </div>
          )}

          {/* Embed */}
          <div
            className="bg-[#2b2d31] rounded-r-md rounded-l-sm overflow-hidden max-w-md"
            style={{ borderLeft: `4px solid ${YOUTUBE_RED}` }}
          >
            <div className="p-3 pb-2">
              <div className="flex items-center gap-1.5 mb-1">
                <span className="material-symbols-outlined text-[#ff0000] text-[14px]">
                  smart_display
                </span>
                <span className="text-xs text-[#dbdee1] hover:underline cursor-pointer font-medium">
                  {SAMPLE_CHANNEL}
                </span>
              </div>
              <p className="font-bold text-[#00a8fc] text-sm leading-tight hover:underline cursor-pointer">
                {SAMPLE_VIDEO_TITLE}
              </p>
              <p className="text-sm text-[#dbdee1] mt-1.5 leading-relaxed">
                {SAMPLE_VIDEO_DESC}
              </p>
            </div>
            <div className="px-3 pb-3">
              <div className="rounded-md overflow-hidden aspect-video">
                <img className="w-full h-full object-cover" src={SAMPLE_THUMBNAIL} alt="Thumbnail" />
              </div>
            </div>
            <div className="px-3 pb-3 text-[11px] text-[#949ba4] flex items-center gap-1">
              <span>YouTube</span>
              <span>·</span>
              <span>{time}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
