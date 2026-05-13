/**
 * Lista de cogs cargados con diseño glassmorphism zen.
 * Cada item muestra nombre, icono, estado activo y descripción.
 */

interface PluginListProps {
  plugins: string[];
  onNavigate?: (section: string) => void;
}

const PLUGIN_META: Record<string, { icon: string; description: string }> = {
  about: {
    icon: 'info',
    description: 'Información del bot y estado del sistema.',
  },
  moderation: {
    icon: 'gavel',
    description: 'Herramientas de protección y orden.',
  },
  music: {
    icon: 'library_music',
    description: 'Armonía sonora para canales de voz.',
  },
  economy: {
    icon: 'payments',
    description: 'Sistema de moneda virtual y recompensas.',
  },
  roles: {
    icon: 'label',
    description: 'Asignación automática de roles.',
  },
};

function formatPluginName(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export default function PluginList({ plugins, onNavigate }: PluginListProps) {
  if (plugins.length === 0) {
    return (
      <section aria-label="Plugins" className="min-h-[calc(100vh-7rem)] -mx-margin-desktop -mt-8 px-margin-desktop pt-12 pb-20">
        <div className="flex flex-col items-center justify-center text-center py-20">
          <span className="material-symbols-outlined text-6xl text-outline-variant mb-4">
            extension_off
          </span>
          <h3 className="font-headline-md text-headline-md text-tertiary">
            No hay plugins cargados
          </h3>
          <p className="text-body-md text-tertiary mt-2">
            Parece que tu bot está en un estado de vacío puro.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="Plugins" className="min-h-[calc(100vh-7rem)] -mx-margin-desktop -mt-8 px-margin-desktop pt-12 pb-20">
      <div className="max-w-container-max mx-auto">
        <div className="mb-10">
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl">
            Gestiona los módulos activos de tu comunidad. Cada plugin está
            diseñado para ofrecer una experiencia equilibrada y eficiente.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter">
          {plugins.map((name) => {
            const meta = PLUGIN_META[name] ?? {
              icon: 'extension',
              description: 'Módulo funcional activo.',
            };

            return (
              <div
                key={name}
                className="glass-panel p-6 rounded-xl border border-white/40 shadow-[0px_10px_30px_rgba(168,0,33,0.03)] hover:shadow-[0px_15px_40px_rgba(168,0,33,0.08)] transition-all duration-500 group flex flex-col justify-between h-64"
              >
                <div className="flex justify-between items-start">
                  <div className="w-12 h-12 bg-secondary/10 rounded-lg flex items-center justify-center text-secondary">
                    <span className="material-symbols-outlined text-[28px]">
                      {meta.icon}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 px-3 py-1 bg-green-100/50 rounded-full">
                    <span className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-label-sm font-label-sm text-green-700">
                      Activo
                    </span>
                  </div>
                </div>

                <div>
                  <h3 className="font-headline-md text-headline-md text-on-surface mb-2">
                    {formatPluginName(name)}
                  </h3>
                  <p className="text-label-sm text-tertiary line-clamp-2">
                    {meta.description}
                  </p>
                </div>

                <div className="flex justify-between items-center mt-4">
                  <span className="text-label-sm text-secondary font-bold cursor-pointer hover:underline">
                    Configurar
                  </span>
                  <span className="material-symbols-outlined text-outline-variant group-hover:text-secondary transition-colors">
                    arrow_forward
                  </span>
                </div>
              </div>
            );
          })}

          {/* YouTube Plugin Card */}
          <div className="glass-panel p-6 rounded-xl border border-white/40 shadow-[0px_10px_30px_rgba(168,0,33,0.03)] hover:shadow-[0px_15px_40px_rgba(168,0,33,0.08)] transition-all duration-500 group flex flex-col justify-between h-64">
            <div className="flex justify-between items-start">
              <div className="w-12 h-12 bg-secondary/10 rounded-lg flex items-center justify-center text-secondary">
                <span className="material-symbols-outlined text-[28px]">smart_display</span>
              </div>
              <div className="flex items-center gap-2 px-3 py-1 bg-green-100/50 rounded-full">
                <span className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse" />
                <span className="text-label-sm font-label-sm text-green-700">Activo</span>
              </div>
            </div>
            <div>
              <h3 className="font-headline-md text-headline-md text-on-surface mb-2">YouTube</h3>
              <p className="text-label-sm text-tertiary line-clamp-2">
                Notificaciones de nuevos videos de YouTube con PubSubHubbub.
              </p>
            </div>
            <button
              onClick={() => onNavigate?.('youtube')}
              className="flex justify-between items-center mt-4 w-full text-left"
            >
              <span className="text-label-sm text-secondary font-bold cursor-pointer hover:underline">
                Configurar
              </span>
              <span className="material-symbols-outlined text-outline-variant group-hover:text-secondary transition-colors">
                arrow_forward
              </span>
            </button>
          </div>
        </div>

        {/* Footer subtle decoration */}
        <div className="mt-20 flex justify-center opacity-10">
          <svg
            width="200"
            height="40"
            viewBox="0 0 200 40"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M0 20C20 20 30 10 50 10C70 10 80 30 100 30C120 30 130 10 150 10C170 10 180 20 200 20"
              stroke="#b71329"
              strokeWidth="2"
            />
          </svg>
        </div>
      </div>
    </section>
  );
}
