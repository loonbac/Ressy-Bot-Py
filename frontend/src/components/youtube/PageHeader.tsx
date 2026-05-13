export default function PageHeader() {
  return (
    <div className="flex-shrink-0">
      <div className="flex items-center gap-2 text-on-surface-variant text-label-sm mb-2">
        <span className="hover:text-secondary cursor-pointer transition-colors">Plugins</span>
        <span className="material-symbols-outlined text-[14px]">chevron_right</span>
        <span className="text-secondary font-semibold">YouTube</span>
      </div>
      <h2 className="font-display text-headline-lg text-on-surface mb-1">
        Configuración de YouTube
      </h2>
      <p className="text-body-md text-on-surface-variant max-w-2xl">
        Sincroniza y gestiona las alertas de tus canales favoritos con la armonía del santuario.
      </p>
    </div>
  );
}
