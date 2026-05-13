export default function ToggleSwitch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={
        'w-10 h-5 rounded-full relative transition-colors duration-300 ' +
        (checked ? 'bg-secondary' : 'bg-outline-variant/30')
      }
    >
      <span
        className={
          'absolute top-1 w-3 h-3 bg-white rounded-full transition-all duration-300 shadow-sm ' +
          (checked ? 'right-1' : 'left-1')
        }
      />
    </button>
  );
}
