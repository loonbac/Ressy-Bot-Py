import { useEffect, useRef, useState } from 'react';
import type { WelcomeConfig } from '@/api/welcome';
import './ColorPickerCard.css';
import './animations.css';

interface Props {
  config: WelcomeConfig;
  onChange: <K extends keyof WelcomeConfig>(key: K, value: WelcomeConfig[K]) => void;
}

const PRESETS: Array<{ name: string; value: number }> = [
  { name: 'Korosoft', value: 0x23856b },
  { name: 'Sakura', value: 0xf7cfd8 },
  { name: 'Hanko', value: 0xa80021 },
  { name: 'Sumi', value: 0x1a1a1a },
  { name: 'Indigo', value: 0x5865f2 },
  { name: 'Ocean', value: 0x0ea5e9 },
  { name: 'Moss', value: 0x4ade80 },
  { name: 'Amber', value: 0xf59e0b },
  { name: 'Lilac', value: 0xa78bfa },
  { name: 'Slate', value: 0x64748b },
];

function toHex(value: number | undefined | null): string {
  const safe = typeof value === 'number' && !Number.isNaN(value) ? value : 0x23856b;
  return `#${safe.toString(16).padStart(6, '0').toUpperCase()}`;
}

function fromHex(hex: string): number | null {
  const cleaned = hex.replace('#', '').trim();
  if (!/^[0-9a-fA-F]{6}$/.test(cleaned)) return null;
  return parseInt(cleaned, 16);
}

export default function ColorPickerCard({ config, onChange }: Props) {
  const currentHex = toHex(config.embed_color);
  const [hexInput, setHexInput] = useState(currentHex);
  const [error, setError] = useState(false);
  const [popKey, setPopKey] = useState(0);
  const hexInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setHexInput(currentHex);
    setError(false);
  }, [currentHex]);

  const selectPreset = (value: number) => {
    onChange('embed_color', value);
    setPopKey((k) => k + 1);
  };

  const commitHex = (raw: string) => {
    const parsed = fromHex(raw);
    if (parsed === null) {
      setError(true);
      hexInputRef.current?.classList.remove('animate-shake');
      // Force reflow then re-add to retrigger animation
      void hexInputRef.current?.offsetWidth;
      hexInputRef.current?.classList.add('animate-shake');
      return;
    }
    setError(false);
    onChange('embed_color', parsed);
  };

  return (
    <div className="welcome-color-card rounded-2xl p-3 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <h3 className="font-headline-md text-base text-primary mb-2 flex items-center gap-2 flex-shrink-0 leading-none">
        <span
          className="material-symbols-outlined text-[18px]"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          palette
        </span>
        Color del Embed
      </h3>

      {/* Inline bar: native color picker + hex input */}
      <div className="welcome-color-card__swatch-bar rounded-lg p-1 mb-2 flex items-center gap-1.5 flex-shrink-0">
        <input
          type="color"
          value={currentHex}
          onChange={(e) => commitHex(e.target.value)}
          className="w-8 h-8 rounded-md bg-transparent border-none cursor-pointer appearance-none flex-shrink-0 [&::-webkit-color-swatch-wrapper]:p-0 [&::-webkit-color-swatch]:border-none [&::-webkit-color-swatch]:rounded-md"
          aria-label="Selector de color"
        />
        <input
          ref={hexInputRef}
          type="text"
          value={hexInput}
          onChange={(e) => {
            setHexInput(e.target.value);
            setError(false);
          }}
          onBlur={() => commitHex(hexInput)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitHex(hexInput);
          }}
          placeholder="#23856B"
          className={
            'welcome-color-card__hex-input flex-1 min-w-0 rounded-md py-1 px-2 text-xs font-mono tracking-wider outline-none uppercase ' +
            (error ? 'is-error' : '')
          }
        />
      </div>

      {/* Palette: 5 cols × 2 rows, fills remaining space */}
      <div
        className="flex-1 min-h-0 grid grid-cols-5 gap-1.5"
        style={{ gridTemplateRows: 'repeat(2, minmax(0, 1fr))' }}
      >
        {PRESETS.map((p) => {
          const selected = p.value === config.embed_color;
          return (
            <button
              key={p.value}
              type="button"
              onClick={() => selectPreset(p.value)}
              title={`${p.name} · ${toHex(p.value)}`}
              className={
                'welcome-color-card__palette-btn rounded-md min-h-0 ' +
                (selected ? `is-selected animate-welcome-swatch-pop` : '')
              }
              data-pop={selected ? popKey : undefined}
              style={{ backgroundColor: toHex(p.value) }}
            />
          );
        })}
      </div>
    </div>
  );
}
