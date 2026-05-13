import { useEffect, useMemo, useRef, useState } from 'react';
import './SearchPalette.css';

interface SearchEntry {
  id: string;
  label: string;
  icon: string;
  keywords: string;
}

const ENTRIES: SearchEntry[] = [
  { id: 'status', label: 'Estado del Sistema', icon: 'analytics', keywords: 'estado uptime latency salud health system' },
  { id: 'plugins', label: 'Plugins', icon: 'extension', keywords: 'plugins módulos cogs' },
  { id: 'config', label: 'Configuración', icon: 'settings', keywords: 'configuracion config settings ajustes prefix' },
  { id: 'welcome', label: 'Bienvenida', icon: 'waving_hand', keywords: 'bienvenida welcome saludo nuevos miembros embed' },
  { id: 'youtube', label: 'YouTube', icon: 'smart_display', keywords: 'youtube videos canales notificaciones rss' },
  { id: 'blackboard', label: 'Blackboard', icon: 'school', keywords: 'blackboard senati tareas asignaciones scraper' },
];

interface Props {
  onNavigate: (section: string) => void;
}

export default function SearchPalette({ onNavigate }: Props) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ENTRIES;
    return ENTRIES.filter((e) =>
      `${e.label} ${e.keywords}`.toLowerCase().includes(q),
    );
  }, [query]);

  // Global Cmd/Ctrl+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (e.key === 'Escape') {
        setOpen(false);
        inputRef.current?.blur();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    setActiveIdx(0);
  }, [query, open]);

  const choose = (id: string) => {
    onNavigate(id);
    setQuery('');
    setOpen(false);
    inputRef.current?.blur();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const hit = results[activeIdx];
      if (hit) choose(hit.id);
    }
  };

  const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform);
  const shortcut = isMac ? '⌘K' : 'Ctrl K';

  return (
    <div ref={wrapperRef} className="topbar-search">
      <div className="relative">
        <span className="absolute inset-y-0 left-3 flex items-center text-outline pointer-events-none">
          <span className="material-symbols-outlined text-[20px]">search</span>
        </span>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Buscar sección..."
          className="topbar-search__input pl-10 pr-16 py-2 text-body-md rounded-full w-72"
        />
        <span className="topbar-search__shortcut absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-bold px-1.5 py-0.5 rounded">
          {shortcut}
        </span>
      </div>

      {open && results.length > 0 && (
        <div className="topbar-search__results absolute right-0 mt-2 w-80 max-h-96 overflow-y-auto rounded-xl p-1 z-50">
          {results.map((r, idx) => (
            <button
              key={r.id}
              type="button"
              onMouseEnter={() => setActiveIdx(idx)}
              onClick={() => choose(r.id)}
              className={
                'topbar-search__result w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left ' +
                (idx === activeIdx ? 'is-active' : '')
              }
            >
              <span className="topbar-search__result-icon w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="material-symbols-outlined text-[18px]">{r.icon}</span>
              </span>
              <span className="flex-1 text-sm font-medium">{r.label}</span>
              <span className="material-symbols-outlined text-[16px] text-tertiary">
                arrow_forward
              </span>
            </button>
          ))}
        </div>
      )}
      {open && results.length === 0 && (
        <div className="topbar-search__results absolute right-0 mt-2 w-80 rounded-xl p-4 z-50 text-center text-sm text-tertiary">
          Nada coincide con "{query}"
        </div>
      )}
    </div>
  );
}
