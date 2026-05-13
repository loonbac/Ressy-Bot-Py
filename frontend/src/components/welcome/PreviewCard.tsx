import type { ReactNode } from 'react';
import type { WelcomeConfig } from '@/api/welcome';
import WelcomeBannerPreview from './WelcomeBannerPreview';
import './PreviewCard.css';

interface Props {
  config: WelcomeConfig;
  botName?: string;
  botAvatarUrl?: string;
}

const SAMPLE_USERNAME = 'ZenMaster';
const SAMPLE_MEMBER_COUNT = '1.234';
const SAMPLE_SERVER = 'Korosoft Community';

function renderTokens(template: string): ReactNode[] {
  const parts = template.split(/(\{user\}|\{user_name\}|\{server\}|\{member_count\}|\{\{user\}\})/g);
  return parts.map((part, idx) => {
    if (part === '{user}' || part === '{{user}}') {
      return (
        <span
          key={idx}
          className="text-[#949cf7] bg-[#3c4270] rounded px-0.5 mx-0.5 hover:bg-[#5865f2] hover:text-white cursor-pointer transition-colors"
        >
          @{SAMPLE_USERNAME}
        </span>
      );
    }
    if (part === '{user_name}') {
      return <span key={idx}>{SAMPLE_USERNAME}</span>;
    }
    if (part === '{server}') {
      return <span key={idx}>{SAMPLE_SERVER}</span>;
    }
    if (part === '{member_count}') {
      return <span key={idx}>{SAMPLE_MEMBER_COUNT}</span>;
    }
    return <span key={idx}>{part}</span>;
  });
}

function toHex(value: number | undefined | null): string {
  const safe = typeof value === 'number' && !Number.isNaN(value) ? value : 0x23856b;
  return `#${safe.toString(16).padStart(6, '0')}`;
}

export default function PreviewCard({ config, botName, botAvatarUrl }: Props) {
  const now = new Date();
  const time = `${now.getHours().toString().padStart(2, '0')}:${now
    .getMinutes()
    .toString()
    .padStart(2, '0')}`;
  const displayBotName = botName || 'Ressy Bot';
  const accentHex = toHex(config.embed_color);

  return (
    <div className="welcome-preview-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <h3 className="font-headline-md text-headline-md text-primary mb-3 flex items-center gap-2 flex-shrink-0 leading-none">
        <span className="material-symbols-outlined text-[22px]">visibility</span>
        Vista Previa
      </h3>

      <div className="bg-[#313338] rounded-xl p-4 text-[#dbdee1] font-sans shadow-xl flex-1 min-h-0 overflow-y-auto">
        <div className="flex gap-3">
          <div className="w-10 h-10 rounded-full flex-shrink-0 overflow-hidden bg-secondary flex items-center justify-center">
            {botAvatarUrl ? (
              <img src={botAvatarUrl} alt={displayBotName} className="w-full h-full object-cover" />
            ) : (
              <span className="material-symbols-outlined text-white">smart_toy</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="font-bold text-white text-[15px] hover:underline cursor-pointer">
                {displayBotName}
              </span>
              <span className="bg-[#5865f2] text-[10px] px-1 rounded-sm text-white font-bold uppercase py-0.5">
                BOT
              </span>
              <span className="text-xs text-[#949ba4] ml-1">Hoy a las {time}</span>
            </div>

            <div
              className="bg-[#2b2d31] rounded-r-md rounded-l-sm overflow-hidden"
              style={{ borderLeft: `4px solid ${accentHex}` }}
            >
              <div className="p-3 pb-2">
                <p className="font-bold text-white text-[15px] leading-tight">
                  {renderTokens(config.embed_title || 'Bienvenid@')}
                </p>
                <div className="text-sm text-[#dbdee1] leading-relaxed mt-2 break-words whitespace-pre-line">
                  {renderTokens(config.welcome_message)}
                </div>
              </div>
              <div className="px-3 pb-3">
                <WelcomeBannerPreview
                  backgroundUrl={config.welcome_image_url}
                  avatarUrl={botAvatarUrl}
                  username={displayBotName}
                  accentHex={accentHex}
                />
              </div>
              <div className="px-3 pb-3 text-[11px] text-[#949ba4]">
                {SAMPLE_SERVER} · Miembro #{SAMPLE_MEMBER_COUNT}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
