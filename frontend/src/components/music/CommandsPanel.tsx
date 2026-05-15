import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ALL_COMMANDS, type MusicConfig } from '@/api/music';
import CommandsCard from './CommandsCard';
import './CommandsPanel.css';
import './animations.css';

interface Props {
  open: boolean;
  config: MusicConfig;
  onClose: () => void;
  onChange: <K extends keyof MusicConfig>(key: K, value: MusicConfig[K]) => void;
}

export default function CommandsPanel({ open, config, onClose, onChange }: Props) {
  // ESC closes the drawer
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Lock body scroll while open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <>
      <div
        className={`music-commands-panel__backdrop ${
          open ? 'music-commands-panel__backdrop--open' : ''
        }`}
        onClick={onClose}
        aria-hidden
      />

      <aside
        className={`music-commands-panel ${open ? 'music-commands-panel--open' : ''}`}
        aria-hidden={!open}
        aria-label="Panel de comandos de música"
      >
        <button
          type="button"
          onClick={onClose}
          className="music-commands-panel__handle"
          aria-label="Cerrar panel"
        >
          <span
            className="material-symbols-outlined text-[20px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            chevron_right
          </span>
        </button>

        <header className="music-commands-panel__header">
          <button
            type="button"
            onClick={onClose}
            className="music-commands-panel__close"
            aria-label="Cerrar panel"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
          <p className="text-[11px] uppercase tracking-widest text-tertiary mb-1">
            Panel de comandos
          </p>
          <h3 className="font-headline-md text-headline-md text-primary">
            Comandos de Música
          </h3>
          <p className="text-sm text-tertiary mt-1 max-w-sm">
            Activa o desactiva qué slash commands están disponibles para los miembros del
            servidor. Los cambios se aplican al guardar.
          </p>
        </header>

        <div className="music-commands-panel__body">
          <CommandsCard
            config={config}
            onChange={onChange}
            layout="list"
            hideHeader
          />
        </div>

        <footer className="music-commands-panel__footer">
          <span>
            {config.enabled_commands.length} / {ALL_COMMANDS.length} comandos activos
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-surface-container-high text-[10px] font-mono">
              Esc
            </kbd>
            para cerrar
          </span>
        </footer>
      </aside>
    </>,
    document.body,
  );
}
