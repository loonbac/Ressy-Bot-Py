interface Props {
  state: 'idle' | 'saving' | 'success' | 'error';
  dirty?: boolean;
  onClick: () => void;
  label?: string;
  disabled?: boolean;
  fullWidth?: boolean;
}

export default function AnimatedSaveButton({ state, dirty, onClick, label, disabled, fullWidth }: Props) {
  const finalLabel =
    state === 'saving'
      ? 'Guardando...'
      : state === 'success'
        ? '¡Guardado!'
        : state === 'error'
          ? 'Error'
          : dirty
            ? label ?? 'Guardar cambios'
            : 'Sin cambios';

  const icon =
    state === 'success'
      ? 'check'
      : state === 'error'
        ? 'error'
        : state === 'saving'
          ? 'progress_activity'
          : 'save';

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || (!dirty && state === 'idle') || state === 'saving'}
      className={`ai-chat-save-btn ${fullWidth ? 'w-full justify-center' : ''} ${
        state === 'success' ? 'animate-ai-chat-bloom' : ''
      } ${state === 'error' ? 'animate-ai-chat-shake' : ''}`}
    >
      <span className={`material-symbols-outlined text-[16px] ${state === 'saving' ? 'animate-ai-chat-spin' : ''}`}>
        {icon}
      </span>
      <span>{finalLabel}</span>
    </button>
  );
}
