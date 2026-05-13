import { ReactNode } from 'react';
import SearchPalette from './topbar/SearchPalette';
import NotificationsBell from './topbar/NotificationsBell';

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
          <div className="flex items-center gap-4">
            <SearchPalette onNavigate={onNavigate} />
            <NotificationsBell />
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
