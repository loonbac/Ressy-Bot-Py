import './AnimatedSaveButton.css';

export type SaveState = 'idle' | 'saving' | 'success' | 'error';

const CONFIG: Record<
  SaveState,
  { icon: string; label: string; fill: boolean; iconAnim: string; btnAnim: string }
> = {
  idle:    { icon: 'save',              label: 'Guardar Armonía',    fill: true,  iconAnim: '',                btnAnim: '' },
  saving:  { icon: 'progress_activity', label: 'Guardando...',       fill: false, iconAnim: 'animate-spin',    btnAnim: '' },
  success: { icon: 'check_circle',      label: '¡Guardado!',         fill: true,  iconAnim: 'animate-spin-in', btnAnim: 'animate-btn-success' },
  error:   { icon: 'error',             label: 'Error al guardar',   fill: true,  iconAnim: 'animate-spin-in', btnAnim: 'animate-shake' },
};

export default function AnimatedSaveButton({
  state,
  onClick,
}: {
  state: SaveState;
  onClick: () => void;
}) {
  const { icon, label, fill, iconAnim, btnAnim } = CONFIG[state];
  return (
    <button
      onClick={onClick}
      disabled={state === 'saving'}
      className={`music-save-btn px-5 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed bloom-btn ${btnAnim}`}
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
