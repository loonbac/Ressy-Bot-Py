/**
 * Lista de plugins con diseño glassmorphism zen.
 * Unifica cogs dinámicos (loaded_cogs) y plugins con UI propia (welcome, youtube).
 */
import './PluginList.css';

interface PluginListProps {
  plugins: string[];
  onNavigate?: (section: string) => void;
}

interface PluginCard {
  key: string;
  title: string;
  icon: string;
  description: string;
  section?: string;
  order: number;
}

const STATIC_PLUGINS: PluginCard[] = [
  {
    key: 'welcome',
    title: 'Bienvenida',
    icon: 'waving_hand',
    description: 'Saludo automático a nuevos miembros con embed personalizable.',
    section: 'welcome',
    order: 10,
  },
  {
    key: 'blackboard',
    title: 'Blackboard',
    icon: 'school',
    description: 'Notificaciones de tareas y asignaciones de Blackboard.',
    section: 'blackboard',
    order: 15,
  },
  {
    key: 'youtube',
    title: 'YouTube',
    icon: 'smart_display',
    description: 'Notificaciones de nuevos videos de YouTube con PubSubHubbub.',
    section: 'youtube',
    order: 20,
  },
];

const COG_META: Record<string, { title: string; icon: string; description: string; order: number }> = {
  moderation: {
    title: 'Moderación',
    icon: 'gavel',
    description: 'Herramientas de protección y orden.',
    order: 40,
  },
  music: {
    title: 'Música',
    icon: 'library_music',
    description: 'Armonía sonora para canales de voz.',
    order: 50,
  },
  economy: {
    title: 'Economía',
    icon: 'payments',
    description: 'Sistema de moneda virtual y recompensas.',
    order: 60,
  },
  roles: {
    title: 'Roles',
    icon: 'label',
    description: 'Asignación automática de roles.',
    order: 70,
  },
};

const HIDDEN_COGS = new Set([
  'welcomecog',
  'welcome',
  'youtubecog',
  'youtube',
  'youtubenotifier',
  'blackboardcog',
  'blackboard',
]);

function buildCards(plugins: string[]): PluginCard[] {
  const cards = [...STATIC_PLUGINS];
  for (const name of plugins) {
    if (HIDDEN_COGS.has(name.toLowerCase())) continue;
    const meta = COG_META[name.toLowerCase()];
    if (meta) {
      cards.push({
        key: name,
        title: meta.title,
        icon: meta.icon,
        description: meta.description,
        order: meta.order,
      });
    } else {
      cards.push({
        key: name,
        title: name.charAt(0).toUpperCase() + name.slice(1),
        icon: 'extension',
        description: 'Módulo funcional activo.',
        order: 100,
      });
    }
  }
  return cards.sort((a, b) => a.order - b.order);
}

export default function PluginList({ plugins, onNavigate }: PluginListProps) {
  const cards = buildCards(plugins);

  if (cards.length === 0) {
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

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter auto-rows-fr">
          {cards.map((card) => {
            const interactive = Boolean(card.section);
            const handleClick = () => {
              if (card.section) onNavigate?.(card.section);
            };
            return (
              <div
                key={card.key}
                className="plugin-card p-6 rounded-xl group flex flex-col justify-between h-64"
              >
                <div className="flex justify-between items-start">
                  <div className="plugin-card__icon w-12 h-12 rounded-lg flex items-center justify-center">
                    <span className="material-symbols-outlined text-[28px]">{card.icon}</span>
                  </div>
                  <div className="plugin-card__active-pill flex items-center gap-2 px-3 py-1 rounded-full">
                    <span className="plugin-card__dot w-2.5 h-2.5 rounded-full animate-pulse" />
                    <span className="text-label-sm font-label-sm">Activo</span>
                  </div>
                </div>

                <div>
                  <h3 className="font-headline-md text-headline-md text-on-surface mb-2">
                    {card.title}
                  </h3>
                  <p className="text-label-sm text-tertiary line-clamp-2">{card.description}</p>
                </div>

                {interactive ? (
                  <button
                    type="button"
                    onClick={handleClick}
                    className="flex justify-between items-center mt-4 w-full text-left"
                  >
                    <span className="plugin-card__cta text-label-sm font-bold hover:underline">
                      Configurar
                    </span>
                    <span className="plugin-card__cta-arrow material-symbols-outlined">
                      arrow_forward
                    </span>
                  </button>
                ) : (
                  <div className="plugin-card__locked flex justify-between items-center mt-4">
                    <span className="text-label-sm font-bold">Sin configuración</span>
                    <span className="material-symbols-outlined">lock</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

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
