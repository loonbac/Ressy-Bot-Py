interface Props {
  onBack?: () => void;
}

export default function PageHeader({ onBack }: Props) {
  return (
    <div className="flex items-center gap-2 text-on-surface-variant text-label-sm flex-shrink-0">
      <button
        type="button"
        onClick={onBack}
        className="hover:text-secondary cursor-pointer transition-colors"
      >
        Plugins
      </button>
      <span className="material-symbols-outlined text-[14px]">chevron_right</span>
      <span className="text-secondary font-semibold">Bienvenida</span>
    </div>
  );
}
