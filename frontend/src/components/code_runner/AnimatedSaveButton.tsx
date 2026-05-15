interface Props {
  state: 'idle' | 'saving' | 'success' | 'error';
  dirty?: boolean;
  onClick: () => void;
  label?: string;
  disabled?: boolean;
}

export default function AnimatedSaveButton({ state, dirty, onClick, label, disabled }: Props) {
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
    state === 'success' ? 'check' : state === 'error' ? 'error' : state === 'saving' ? 'progress_activity' : 'save';

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || (!dirty && state === 'idle') || state === 'saving'}
      className={`cr-save-btn ${state === 'success' ? 'animate-cr-bloom' : ''} ${state === 'error' ? 'animate-cr-shake' : ''}`}
    >
      <span className={`material-symbols-outlined text-[16px] ${state === 'saving' ? 'animate-cr-spin' : ''}`}>
        {icon}
      </span>
      <span>{finalLabel}</span>
    </button>
  );
}
