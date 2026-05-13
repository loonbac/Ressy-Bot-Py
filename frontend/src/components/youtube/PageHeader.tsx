export default function PageHeader() {
  return (
    <div className="flex items-center gap-2 text-on-surface-variant text-label-sm flex-shrink-0">
      <span className="hover:text-secondary cursor-pointer transition-colors">Plugins</span>
      <span className="material-symbols-outlined text-[14px]">chevron_right</span>
      <span className="text-secondary font-semibold">YouTube</span>
    </div>
  );
}
