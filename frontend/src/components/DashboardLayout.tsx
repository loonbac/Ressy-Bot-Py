import { ReactNode } from 'react';

interface DashboardLayoutProps {
  title: string;
  activeSection: string;
  onNavigate: (section: string) => void;
  children: ReactNode;
  botAvatarUrl?: string;
  botName?: string;
}

export default function DashboardLayout({
  title,
  activeSection,
  onNavigate,
  children,
  botAvatarUrl,
  botName,
}: DashboardLayoutProps) {
  const navItems = [
    { id: 'status', label: 'Estado', icon: 'analytics' },
    { id: 'plugins', label: 'Plugins', icon: 'extension' },
    { id: 'config', label: 'Configuración', icon: 'settings' },
  ];

  return (
    <div className="min-h-screen">
      {/* SideNavBar */}
      <aside className="h-screen w-64 fixed left-0 top-0 bg-surface/80 backdrop-blur-md border-r border-outline-variant/30 shadow-[0px_10px_30px_rgba(168,0,33,0.05)] flex flex-col py-8 px-6 z-50">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-10 h-10 rounded-full overflow-hidden border border-outline-variant/50">
            {botAvatarUrl ? (
              <img
                alt={botName || 'Bot'}
                className="w-full h-full object-cover"
                src={botAvatarUrl}
              />
            ) : (
              <div className="w-full h-full bg-primary-container flex items-center justify-center">
                <span className="material-symbols-outlined text-primary">smart_toy</span>
              </div>
            )}
          </div>
          <div>
            <h1 className="font-headline-md text-headline-md text-primary leading-none">
              Ressy Bot
            </h1>
            <p className="font-label-sm text-label-sm text-tertiary uppercase tracking-widest mt-1">
              {botName ? `${botName} Bot` : 'Korosoft Bot'}
            </p>
          </div>
        </div>

        <nav className="flex-grow space-y-4">
          {navItems.map((item) => {
            const isActive = activeSection === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={
                  'w-full flex items-center gap-4 px-4 py-3 rounded-lg text-left transition-all duration-300 active:scale-[0.98] ' +
                  (isActive
                    ? 'text-secondary border-l-4 border-secondary font-bold bg-secondary-container/10'
                    : 'text-tertiary hover:text-primary hover:bg-primary-container/20')
                }
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                <span className="font-body-md text-body-md">{item.label}</span>
              </button>
            );
          })}
        </nav>

      </aside>

      {/* TopAppBar */}
      <header className="fixed top-0 right-0 w-[calc(100%-16rem)] h-20 z-40 bg-surface/60 backdrop-blur-xl border-b border-outline-variant/20">
        <div className="h-full max-w-container-max mx-auto px-margin-desktop flex justify-between items-center">
          <h2 className="font-headline-md text-headline-md text-primary">{title}</h2>
          <div className="flex items-center gap-6">
            <div className="relative group">
              <span className="absolute inset-y-0 left-3 flex items-center text-outline">
                <span className="material-symbols-outlined text-[20px]">search</span>
              </span>
              <input
                className="bg-surface-container-low border-none focus:ring-0 focus:border-secondary text-body-md pl-10 pr-4 py-2 rounded-full w-64 transition-all"
                placeholder="Buscar..."
                type="text"
              />
            </div>
            <div className="flex items-center gap-4">
              <button className="text-on-surface-variant hover:text-secondary transition-colors">
                <span className="material-symbols-outlined">notifications</span>
              </button>
              <button className="text-on-surface-variant hover:text-secondary transition-colors">
                <span className="material-symbols-outlined">settings_heart</span>
              </button>
              <div className="w-10 h-10 rounded-full bg-primary-container/30 border border-outline-variant/30 flex items-center justify-center overflow-hidden">
                <img
                  alt="User Avatar"
                  className="w-full h-full object-cover"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuAJJ8uP12K1ma9_HIviehy5h2gEMxi7HLP6iCdwT6Nh2z8glQZ70mczkU1nxt2LyViQH3YM_2O3mk-WktcFV_D3tZAmO8j1E-LEwkZFcjZPAxkIkulOXWACyzElDQnMb-40xDq6LiBnwtQEYjr4HsydwT66-dWG06XZTw9XCSfjtgCOcamueypdytSXnN8rjF42n0COJzEpM-hy3LTUnmRl_jW41n6Hi5znlmo1BAjQdKJcU873JMpLWpGxWhrGanc8Em011Kr5ghg"
                />
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Canvas */}
      <main className="ml-64 pt-28 px-margin-desktop pb-20 relative z-10">
        <div className="max-w-container-max mx-auto">{children}</div>
      </main>
    </div>
  );
}
