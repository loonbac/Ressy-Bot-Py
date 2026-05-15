import { useState } from 'react';
import './SessionsTable.css';
import type { CodeRunnerSession } from '@/api/code-runner';

interface Props {
  sessions: CodeRunnerSession[];
  onClose: (sessionId: number) => Promise<void>;
}

function formatRelative(ts: number): string {
  if (!ts) return '—';
  const now = Date.now() / 1000;
  const diff = ts - now;
  const abs = Math.abs(diff);
  const mins = Math.floor(abs / 60);
  if (mins < 1) return diff >= 0 ? 'Ahora' : 'Hace segs';
  if (mins < 60) return diff >= 0 ? `En ${mins}m` : `Hace ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return diff >= 0 ? `En ${hours}h` : `Hace ${hours}h`;
  const days = Math.floor(hours / 24);
  return diff >= 0 ? `En ${days}d` : `Hace ${days}d`;
}

function statusPill(status: string): string {
  if (status === 'active') return 'cr-status-pill--ok';
  if (status === 'expired' || status === 'inactive') return 'cr-status-pill--warn';
  if (status === 'closed' || status === 'archived') return 'cr-status-pill--neutral';
  return 'cr-status-pill--neutral';
}

export default function SessionsTable({ sessions, onClose }: Props) {
  const [tab, setTab] = useState<'active' | 'archived'>('active');
  const [closing, setClosing] = useState<number | null>(null);

  const filtered = sessions.filter((s) =>
    tab === 'active' ? s.status === 'active' : s.status !== 'active',
  );

  const handleClose = async (id: number) => {
    if (!window.confirm('¿Cerrar esta sesión y archivar el transcript?')) return;
    setClosing(id);
    try {
      await onClose(id);
    } finally {
      setClosing(null);
    }
  };

  return (
    <div className="cr-card cr-sessions-card animate-cr-card-enter animate-cr-stagger-5">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <span className="cr-card__icon material-symbols-outlined">forum</span>
          <h3 className="font-headline-md text-headline-md text-primary">Sesiones</h3>
        </div>
        <div className="flex gap-4">
          <button
            type="button"
            onClick={() => setTab('active')}
            className={`cr-tab ${tab === 'active' ? 'cr-tab--active' : ''}`}
          >
            Activas ({sessions.filter((s) => s.status === 'active').length})
          </button>
          <button
            type="button"
            onClick={() => setTab('archived')}
            className={`cr-tab ${tab === 'archived' ? 'cr-tab--active' : ''}`}
          >
            Archivadas ({sessions.filter((s) => s.status !== 'active').length})
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-8 text-on-surface-variant text-sm italic">
          {tab === 'active' ? 'No hay sesiones activas en este momento.' : 'No hay sesiones archivadas.'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-outline-variant text-label-sm text-on-surface-variant">
                <th className="pb-3 font-medium uppercase tracking-widest text-[10px]">Usuario</th>
                <th className="pb-3 font-medium uppercase tracking-widest text-[10px]">Canal</th>
                <th className="pb-3 font-medium uppercase tracking-widest text-[10px] text-center">Estado</th>
                <th className="pb-3 font-medium uppercase tracking-widest text-[10px]">Creada</th>
                <th className="pb-3 font-medium uppercase tracking-widest text-[10px]">Expira</th>
                <th className="pb-3 font-medium uppercase tracking-widest text-[10px] text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              {filtered.map((s, idx) => (
                <tr
                  key={s.id}
                  className="cr-sessions-card__row animate-cr-row-fade"
                  style={{ animationDelay: `${idx * 30}ms` }}
                >
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <span className="cr-sessions-card__avatar">
                        {String(s.user_id).slice(-2)}
                      </span>
                      <span className="font-mono text-[12px]">{s.user_id}</span>
                    </div>
                  </td>
                  <td className="py-3 text-on-surface-variant text-[12px] font-mono">{s.channel_id}</td>
                  <td className="py-3 text-center">
                    <span className={`cr-status-pill ${statusPill(s.status)}`}>{s.status}</span>
                  </td>
                  <td className="py-3 text-[12px] text-on-surface-variant">{formatRelative(s.created_at)}</td>
                  <td className="py-3 text-[12px] text-on-surface-variant">
                    {s.status === 'active' ? formatRelative(s.expires_at) : '—'}
                  </td>
                  <td className="py-3 text-right">
                    <div className="flex justify-end gap-1">
                      {s.transcript_path && (
                        <a
                          href={`/api/plugins/code-runner/sessions/${s.id}/transcript`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 text-on-surface-variant hover:text-primary"
                          title="Ver transcript"
                        >
                          <span className="material-symbols-outlined text-[18px]">description</span>
                        </a>
                      )}
                      {s.status === 'active' && (
                        <button
                          type="button"
                          onClick={() => handleClose(s.id)}
                          disabled={closing === s.id}
                          className="p-1 text-on-surface-variant hover:text-error"
                          title="Cerrar sesión"
                        >
                          <span
                            className={`material-symbols-outlined text-[18px] ${closing === s.id ? 'animate-cr-spin' : ''}`}
                          >
                            {closing === s.id ? 'progress_activity' : 'close'}
                          </span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
