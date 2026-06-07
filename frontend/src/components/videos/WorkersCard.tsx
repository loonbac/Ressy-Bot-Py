import { useState } from 'react';
import type { VideoWorker } from '@/api/videos';
import './base.css';
import './WorkersCard.css';

interface Props {
  workers: VideoWorker[];
  managerOnline: boolean;
  onAdd: (token: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onStop: (id: string) => Promise<void>;
}

const STATUS_LABEL: Record<string, string> = {
  idle: 'Disponible',
  playing: 'En vivo',
  offline: 'Apagado',
  error: 'Error',
  unknown: 'Desconocido',
};

export default function WorkersCard({ workers, managerOnline, onAdd, onDelete, onStop }: Props) {
  const [token, setToken] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shakeNonce, setShakeNonce] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);

  const handleAdd = async () => {
    const t = token.trim();
    if (!t) {
      setError('Pega un token de usuario');
      setShakeNonce((n) => n + 1);
      return;
    }
    setAdding(true);
    setError(null);
    try {
      await onAdd(t);
      setToken('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo agregar el worker');
      setShakeNonce((n) => n + 1);
    } finally {
      setAdding(false);
    }
  };

  const rowAction = async (id: string, fn: (id: string) => Promise<void>) => {
    setBusyId(id);
    try {
      await fn(id);
    } catch {
      /* el parent muestra feedback */
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="videos-card p-4 h-full flex flex-col min-h-0 animate-videos-card-enter animate-videos-stagger-2">
      <span className="videos-card__accent" />
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-[20px]"
            style={{ color: '#ff0050', fontVariationSettings: "'FILL' 1" }}
          >
            groups
          </span>
          <h3 className="font-headline-md text-on-surface text-base">Workers (cuentas)</h3>
        </div>
        <span className="text-xs text-on-surface-variant">{workers.length} configurados</span>
      </div>

      {/* Add token form */}
      <div
        key={shakeNonce}
        className={'flex gap-2 mb-2 flex-shrink-0 ' + (error ? 'animate-videos-shake' : '')}
      >
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !adding && handleAdd()}
          placeholder="Token de usuario (selfbot)…"
          className="videos-input flex-1 px-3 py-2 text-sm"
          autoComplete="off"
          spellCheck={false}
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={adding}
          className="videos-btn-primary px-4 py-2 text-sm flex items-center gap-1.5"
        >
          {adding ? (
            <span className="material-symbols-outlined text-[18px] animate-videos-spin">
              progress_activity
            </span>
          ) : (
            <span className="material-symbols-outlined text-[18px]">add</span>
          )}
          {adding ? 'Validando…' : 'Agregar'}
        </button>
      </div>

      {error && (
        <p className="text-xs text-error mb-2 flex items-center gap-1 flex-shrink-0">
          <span className="material-symbols-outlined text-[14px]">error</span>
          {error}
        </p>
      )}
      <p className="text-[0.7rem] text-on-surface-variant mb-3 flex-shrink-0">
        El token es de una cuenta de usuario (selfbot). Úsala desechable y asegúrate de que la cuenta
        sea miembro del servidor. Más workers = más videos simultáneos.
      </p>

      {/* Worker list */}
      <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-2 videos-workers-scroll">
        {workers.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-on-surface-variant gap-2 py-6">
            <span className="material-symbols-outlined text-3xl opacity-40">person_off</span>
            <p className="text-sm">No hay workers. Agrega un token para empezar.</p>
          </div>
        ) : (
          workers.map((w, idx) => {
            const status = w.status || 'unknown';
            const rowBusy = busyId === w.user_id;
            return (
              <div
                key={w.user_id}
                className="videos-worker-row animate-videos-row-in"
                style={{ animationDelay: `${idx * 0.04}s` }}
              >
                <div className="w-9 h-9 rounded-full overflow-hidden flex-shrink-0 bg-surface-container border border-outline-variant/40">
                  {w.avatar_url ? (
                    <img src={w.avatar_url} alt={w.tag} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <span className="material-symbols-outlined text-[18px] text-on-surface-variant">
                        person
                      </span>
                    </div>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-on-surface truncate">
                      {w.tag || w.username || w.user_id}
                    </span>
                    {status === 'playing' && (
                      <span className="videos-live-pill">
                        <span className="videos-dot videos-dot--playing animate-videos-live-blink" />
                        EN VIVO
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[0.7rem] text-on-surface-variant">
                    <span className={'videos-dot videos-dot--' + status} />
                    {STATUS_LABEL[status] ?? status}
                    <span className="opacity-50">· token {w.token_preview}</span>
                  </div>
                </div>

                <div className="flex items-center gap-1 flex-shrink-0">
                  {status === 'playing' && (
                    <button
                      type="button"
                      title="Detener"
                      disabled={rowBusy}
                      onClick={() => rowAction(w.user_id, onStop)}
                      className="videos-worker-icon-btn"
                    >
                      <span className="material-symbols-outlined text-[18px]">stop_circle</span>
                    </button>
                  )}
                  <button
                    type="button"
                    title="Eliminar worker"
                    disabled={rowBusy}
                    onClick={() => rowAction(w.user_id, onDelete)}
                    className="videos-worker-icon-btn videos-worker-icon-btn--danger"
                  >
                    {rowBusy ? (
                      <span className="material-symbols-outlined text-[18px] animate-videos-spin">
                        progress_activity
                      </span>
                    ) : (
                      <span className="material-symbols-outlined text-[18px]">delete</span>
                    )}
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {!managerOnline && workers.length > 0 && (
        <p className="text-[0.7rem] text-amber-600 mt-2 flex items-center gap-1 flex-shrink-0">
          <span className="material-symbols-outlined text-[14px]">warning</span>
          Manager sin conexión: los estados en vivo no están disponibles.
        </p>
      )}
    </div>
  );
}
