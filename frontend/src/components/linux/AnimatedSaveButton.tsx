import './AnimatedSaveButton.css';
import './animations.css';

export type SaveState = 'idle' | 'saving' | 'success' | 'error';

interface Props {
  state: SaveState;
  onClick: () => void;
  disabled?: boolean;
}

const LABELS: Record<SaveState, string> = {
  idle: 'Guardar cambios',
  saving: 'Guardando...',
  success: '¡Guardado!',
  error: 'Reintentar',
};

const ICONS: Record<SaveState, string> = {
  idle: 'save',
  saving: 'progress_activity',
  success: 'check_circle',
  error: 'replay',
};

export default function AnimatedSaveButton({ state, onClick, disabled }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || state === 'saving'}
      className={`linux-save-btn linux-save-btn--${state} flex items-center gap-2 px-5 py-2 rounded-full font-bold text-sm transition-all`}
    >
      <span
        className={`material-symbols-outlined text-[18px] ${state === 'saving' ? 'animate-linux-sync-spin' : ''}`}
        style={{ fontVariationSettings: "'FILL' 1" }}
      >
        {ICONS[state]}
      </span>
      <span>{LABELS[state]}</span>
    </button>
  );
}
