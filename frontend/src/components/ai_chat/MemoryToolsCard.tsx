import { useCallback, useEffect, useState } from 'react';
import './MemoryToolsCard.css';
import {
  fetchMemories,
  createMemory,
  deleteMemory,
  type AIChatMemory,
  type MemoryScope,
} from '@/api/ai-chat';

interface Props {
  showToast: (kind: 'success' | 'error', text: string) => void;
}

function formatDate(epoch: number): string {
  try {
    return new Date(epoch * 1000).toLocaleString('es-PE', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export default function MemoryToolsCard({ showToast }: Props) {
  const [scope, setScope] = useState<MemoryScope>('global');
  const [ownerId, setOwnerId] = useState('');
  const [memories, setMemories] = useState<AIChatMemory[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Para scope 'user' se necesita un owner_id (snowflake) antes de consultar.
  const needsOwner = scope === 'user';
  const canQuery = !needsOwner || ownerId.trim().length > 0;

  const load = useCallback(async () => {
    if (!canQuery) {
      setMemories([]);
      return;
    }
    setLoading(true);
    try {
      const items = await fetchMemories(scope, needsOwner ? ownerId.trim() : undefined);
      setMemories(items);
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error al cargar memorias');
    } finally {
      setLoading(false);
    }
  }, [scope, ownerId, needsOwner, canQuery, showToast]);

  useEffect(() => {
    // Global se consulta solo; user espera a tener owner_id.
    if (scope === 'global') void load();
    else setMemories([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  const handleAdd = async () => {
    const content = draft.trim();
    if (!content) return;
    if (needsOwner && !ownerId.trim()) {
      showToast('error', 'Ingresa el ID de usuario para una memoria de scope user.');
      return;
    }
    setSaving(true);
    try {
      await createMemory({
        content,
        scope,
        owner_id: needsOwner ? ownerId.trim() : null,
      });
      setDraft('');
      showToast('success', 'Memoria guardada');
      await load();
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error al guardar memoria');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await deleteMemory(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
      showToast('success', 'Memoria eliminada');
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error al eliminar memoria');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="ai-chat-card ai-chat-memory-card animate-ai-chat-card-enter animate-ai-chat-stagger-4 w-full flex flex-col">
      <div className="flex items-center gap-3 mb-6">
        <span className="ai-chat-card__icon material-symbols-outlined">memory</span>
        <div>
          <h3 className="font-headline-md text-headline-md text-primary">Memoria de largo plazo</h3>
          <p className="text-[11px] text-on-surface-variant">
            Hechos duraderos que el asistente recuerda entre conversaciones.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 mb-5">
        <div>
          <label className="ai-chat-label">Ámbito</label>
          <div className="ai-chat-select-wrap">
            <select
              className="ai-chat-select"
              value={scope}
              onChange={(e) => setScope(e.target.value as MemoryScope)}
            >
              <option value="global">Global (todo el servidor)</option>
              <option value="user">Usuario específico</option>
            </select>
            <span className="ai-chat-select__chevron material-symbols-outlined">expand_more</span>
          </div>
        </div>
        {needsOwner && (
          <div>
            <label className="ai-chat-label">ID de usuario (Discord)</label>
            <div className="ai-chat-input-wrap">
              <input
                className="ai-chat-input font-mono text-[12px]"
                value={ownerId}
                onChange={(e) => setOwnerId(e.target.value.replace(/[^0-9]/g, ''))}
                onBlur={() => void load()}
                placeholder="123456789012345678"
                inputMode="numeric"
                spellCheck={false}
              />
            </div>
          </div>
        )}
      </div>

      <div className="ai-chat-memory-add mb-5">
        <label className="ai-chat-label">Agregar memoria</label>
        <textarea
          className="ai-chat-textarea"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ej: El servidor es de la comunidad SENATI / Korosoft."
        />
        <div className="flex justify-end mt-2">
          <button
            type="button"
            className="ai-chat-save-btn"
            disabled={saving || !draft.trim() || (needsOwner && !ownerId.trim())}
            onClick={() => void handleAdd()}
          >
            {saving ? (
              <span className="material-symbols-outlined animate-ai-chat-spin">progress_activity</span>
            ) : (
              <span className="material-symbols-outlined">add</span>
            )}
            Guardar
          </button>
        </div>
      </div>

      <div className="ai-chat-memory-list">
        {loading ? (
          <div className="ai-chat-memory-empty">
            <span className="material-symbols-outlined animate-ai-chat-spin">progress_activity</span>
            Cargando memorias…
          </div>
        ) : !canQuery ? (
          <div className="ai-chat-memory-empty">Ingresa un ID de usuario para ver sus memorias.</div>
        ) : memories.length === 0 ? (
          <div className="ai-chat-memory-empty">Sin memorias guardadas en este ámbito.</div>
        ) : (
          memories.map((m) => (
            <div key={m.id} className="ai-chat-memory-row animate-ai-chat-msg-in">
              <div className="ai-chat-memory-row__body">
                <p className="ai-chat-memory-row__content">{m.content}</p>
                <span className="ai-chat-memory-row__meta">
                  {m.source} · {formatDate(m.created_at)}
                </span>
              </div>
              <button
                type="button"
                className="ai-chat-memory-row__delete"
                title="Eliminar memoria"
                disabled={deletingId === m.id}
                onClick={() => void handleDelete(m.id)}
              >
                <span
                  className={`material-symbols-outlined ${deletingId === m.id ? 'animate-ai-chat-spin' : ''}`}
                >
                  {deletingId === m.id ? 'progress_activity' : 'delete'}
                </span>
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
