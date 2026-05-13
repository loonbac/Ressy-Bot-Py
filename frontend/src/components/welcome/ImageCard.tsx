import { useState } from 'react';
import type { WelcomeConfig } from '@/api/welcome';
import './ImageCard.css';
import './animations.css';

interface Props {
  config: WelcomeConfig;
  onChange: <K extends keyof WelcomeConfig>(key: K, value: WelcomeConfig[K]) => void;
}

const PRESETS: Array<{ id: string; url: string; label: string }> = [
  {
    id: 'sakura',
    url: 'https://images.unsplash.com/photo-1522383225653-ed111181a951?w=900&q=70&auto=format&fit=crop',
    label: 'Sakura',
  },
  {
    id: 'torii',
    url: 'https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=900&q=70&auto=format&fit=crop',
    label: 'Torii',
  },
  {
    id: 'mountain',
    url: 'https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=900&q=70&auto=format&fit=crop',
    label: 'Niebla',
  },
];

export default function ImageCard({ config, onChange }: Props) {
  const [customUrl, setCustomUrl] = useState(
    PRESETS.some((p) => p.url === config.welcome_image_url) ? '' : config.welcome_image_url,
  );

  const [popId, setPopId] = useState(0);
  const selectPreset = (url: string) => {
    onChange('welcome_image_url', url);
    setCustomUrl('');
    setPopId((k) => k + 1);
  };

  const applyCustom = () => {
    if (customUrl.trim()) {
      onChange('welcome_image_url', customUrl.trim());
    }
  };

  const clearImage = () => {
    onChange('welcome_image_url', '');
    setCustomUrl('');
  };

  return (
    <div className="welcome-image-card rounded-2xl p-4 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <h3 className="font-headline-md text-headline-md text-primary flex items-center gap-2 leading-none">
          <span className="material-symbols-outlined text-[20px]">image</span>
          Imagen
        </h3>
        {config.welcome_image_url && (
          <button
            type="button"
            onClick={clearImage}
            className="text-label-sm text-tertiary hover:text-error transition-colors flex items-center gap-1"
            title="Quitar imagen"
          >
            <span className="material-symbols-outlined text-[16px]">close</span>
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3 flex-1 min-h-0">
        {PRESETS.map((p) => {
          const selected = config.welcome_image_url === p.url;
          return (
            <button
              type="button"
              key={p.id}
              onClick={() => selectPreset(p.url)}
              title={p.label}
              className={
                'welcome-image-card__preset relative rounded-xl overflow-hidden cursor-pointer min-h-0 ' +
                (selected ? 'is-selected animate-welcome-image-pop' : '')
              }
              data-pop={selected ? popId : undefined}
            >
              <img className="w-full h-full object-cover" src={p.url} alt={p.label} />
              {selected && (
                <div className="absolute inset-0 bg-secondary/30 flex items-center justify-center">
                  <span
                    className="material-symbols-outlined text-white text-2xl"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    check_circle
                  </span>
                </div>
              )}
              <span className="absolute bottom-1 left-1.5 right-1.5 text-[10px] uppercase tracking-wider text-white bg-black/40 px-1.5 py-0.5 rounded text-center">
                {p.label}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex-shrink-0">
        <label className="block text-label-sm uppercase tracking-wider text-primary font-bold mb-1.5">
          URL Personalizada
        </label>
        <div className="flex gap-2">
          <input
            type="url"
            value={customUrl}
            onChange={(e) => setCustomUrl(e.target.value)}
            placeholder="https://..."
            className="welcome-image-card__url flex-1 min-w-0 rounded-lg py-2 px-3 text-sm"
          />
          <button
            type="button"
            onClick={applyCustom}
            disabled={!customUrl.trim()}
            className="welcome-image-card__apply-btn px-3 rounded-lg text-xs font-bold transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-[18px]">cloud_upload</span>
          </button>
        </div>
      </div>
    </div>
  );
}
