import { useEffect, useState } from 'react';

interface Props {
  channelName: string | null;
  onDismiss: () => void;
}

export default function ChannelAddedToast({ channelName, onDismiss }: Props) {
  const [displayed, setDisplayed] = useState<string | null>(null);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (channelName) {
      setDisplayed(channelName);
      setExiting(false);

      const exitTimer = setTimeout(() => setExiting(true), 2400);
      const dismissTimer = setTimeout(() => {
        setDisplayed(null);
        onDismiss();
      }, 2750);

      return () => {
        clearTimeout(exitTimer);
        clearTimeout(dismissTimer);
      };
    }
  }, [channelName, onDismiss]);

  if (!displayed) return null;

  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
      <div className={exiting ? 'animate-toast-out' : 'animate-toast-in'}>
        <div className="relative bg-surface-container-highest border border-outline-variant/30 rounded-2xl px-5 py-3.5 shadow-2xl flex items-center gap-3 min-w-[260px]">
          {/* Sparkle decorations */}
          <span
            className="absolute -top-2 -right-2 material-symbols-outlined text-secondary text-[22px] animate-sparkle-pop"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            auto_awesome
          </span>
          <span
            className="absolute -top-1 right-5 material-symbols-outlined text-primary text-[14px] animate-sparkle-pop"
            style={{ animationDelay: '80ms', fontVariationSettings: "'FILL' 1" }}
          >
            star
          </span>

          {/* Icon */}
          <span
            className="material-symbols-outlined text-[28px] text-green-500 animate-spin-in flex-shrink-0"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            check_circle
          </span>

          {/* Text */}
          <div className="min-w-0">
            <p className="font-label-sm text-secondary uppercase tracking-widest text-xs">
              Canal agregado
            </p>
            <p className="text-on-surface font-medium text-sm truncate">{displayed}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
