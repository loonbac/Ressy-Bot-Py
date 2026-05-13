import './AnimatedTestButton.css';

export type TestState = 'idle' | 'testing' | 'success' | 'error';

const CONFIG: Record<
  TestState,
  { icon: string; label: string; fill: boolean; iconAnim: string; btnAnim: string }
> = {
  idle:    { icon: 'send',              label: 'Enviar Prueba', fill: true,  iconAnim: '',                btnAnim: '' },
  testing: { icon: 'progress_activity', label: 'Enviando...',   fill: false, iconAnim: 'animate-spin',    btnAnim: '' },
  success: { icon: 'check_circle',      label: '¡Enviado!',     fill: true,  iconAnim: 'animate-spin-in', btnAnim: 'animate-btn-success' },
  error:   { icon: 'error',             label: 'Error',         fill: true,  iconAnim: 'animate-spin-in', btnAnim: 'animate-shake' },
};

export default function AnimatedTestButton({
  state,
  onClick,
}: {
  state: TestState;
  onClick: () => void;
}) {
  const { icon, label, fill, iconAnim, btnAnim } = CONFIG[state];
  return (
    <button
      onClick={onClick}
      disabled={state === 'testing'}
      className={`welcome-test-btn px-4 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed bloom-btn ${btnAnim}`}
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
