export type TestState = 'idle' | 'testing' | 'success' | 'error';

const CONFIG: Record<
  TestState,
  { icon: string; label: string; fill: boolean; iconAnim: string; btnAnim: string }
> = {
  idle:    { icon: 'play_arrow',         label: 'Enviar prueba', fill: true,  iconAnim: '',                btnAnim: '' },
  testing: { icon: 'progress_activity',  label: 'Enviando...',   fill: false, iconAnim: 'animate-spin',    btnAnim: '' },
  success: { icon: 'check_circle',       label: '¡Enviado!',     fill: true,  iconAnim: 'animate-spin-in', btnAnim: 'animate-btn-success' },
  error:   { icon: 'error',              label: 'Error',         fill: true,  iconAnim: 'animate-spin-in', btnAnim: 'animate-shake' },
};

export default function AnimatedTestButton({
  state,
  onClick,
  disabled = false,
}: {
  state: TestState;
  onClick: () => void;
  disabled?: boolean;
}) {
  const { icon, label, fill, iconAnim, btnAnim } = CONFIG[state];

  return (
    <button
      onClick={onClick}
      disabled={disabled || state === 'testing'}
      className={`bg-primary-fixed/40 text-on-primary-fixed-variant hover:bg-primary-fixed/60 px-5 py-2 rounded-lg font-label-sm shadow-sm flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed bloom-btn transition-colors ${btnAnim}`}
    >
      <span
        key={state}
        className={`material-symbols-outlined text-[18px] ${iconAnim}`}
        style={fill ? { fontVariationSettings: "'FILL' 1" } : undefined}
      >
        {icon}
      </span>
      {label}
    </button>
  );
}
