import { useRef } from 'react';
import './animations.css';

interface Props {
  checked: boolean;
  onChange: (v: boolean) => void;
  size?: 'sm' | 'md';
  disabled?: boolean;
}

export default function ToggleSwitch({ checked, onChange, size = 'md', disabled }: Props) {
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const dims = size === 'sm' ? 'w-10 h-5' : 'w-14 h-7';
  const knob = size === 'sm' ? 'w-3 h-3 top-1' : 'w-5 h-5 top-1';
  const offset = checked ? 'right-1' : 'left-1';

  const handleClick = () => {
    if (disabled) return;
    onChange(!checked);
    const btn = btnRef.current;
    if (btn) {
      btn.classList.remove('animate-music-toggle-flash');
      void btn.offsetWidth;
      btn.classList.add('animate-music-toggle-flash');
    }
  };

  return (
    <button
      ref={btnRef}
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={handleClick}
      className={
        `${dims} rounded-full relative transition-colors duration-300 flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed ` +
        (checked ? 'bg-secondary' : 'bg-surface-container-highest')
      }
    >
      <span
        className={`absolute ${knob} ${offset} bg-white rounded-full transition-all duration-300 shadow-sm`}
      />
    </button>
  );
}
