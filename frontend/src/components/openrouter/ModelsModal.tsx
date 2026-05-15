import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import './ModelsModal.css';
import type { OpenRouterModel } from '@/api/openrouter';
import { formatPrice, formatContext, PROVIDER_LABELS } from './ModelsTable';

interface Props {
  open: boolean;
  models: OpenRouterModel[];
  total: number;
  onClose: () => void;
  onSelectModel?: (model: OpenRouterModel) => void;
}

type SortKey = 'prompt' | 'completion' | 'context' | 'name' | 'total';
type SortDir = 'asc' | 'desc';

function getProvider(id: string): string {
  const idx = id.indexOf('/');
  if (idx < 0) return 'Otro';
  return id.slice(0, idx);
}

export default function ModelsModal({ open, models, total, onClose, onSelectModel }: Props) {
  const [search, setSearch] = useState('');
  const [provider, setProvider] = useState('all');
  const [onlyFree, setOnlyFree] = useState(false);
  const [onlyText, setOnlyText] = useState(false);
  const [hideVariable, setHideVariable] = useState(false);
  const [sortBy, setSortBy] = useState<SortKey>('total');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  const providers = useMemo(() => {
    const set = new Set<string>();
    models.forEach((m) => set.add(getProvider(m.id)));
    return Array.from(set).sort();
  }, [models]);

  const filtered = useMemo(() => {
    let out = models;
    if (search.trim()) {
      const q = search.toLowerCase();
      out = out.filter(
        (m) =>
          m.id.toLowerCase().includes(q) ||
          (m.name && m.name.toLowerCase().includes(q)),
      );
    }
    if (provider !== 'all') {
      out = out.filter((m) => getProvider(m.id) === provider);
    }
    if (onlyFree) {
      out = out.filter(
        (m) =>
          m.pricing_prompt_per_mtok === 0 &&
          m.pricing_completion_per_mtok === 0,
      );
    }
    if (onlyText) {
      const isText = (m: OpenRouterModel) => {
        const mods = m.modalities ?? [];
        if (mods.length === 0) return true;
        return mods.every((m2) => m2 === 'text');
      };
      out = out.filter(isText);
    }
    if (hideVariable) {
      out = out.filter((m) => {
        const p = m.pricing_prompt_per_mtok;
        const c = m.pricing_completion_per_mtok;
        return p != null && c != null && p >= 0 && c >= 0;
      });
    }
    return out;
  }, [models, search, provider, onlyFree, onlyText, hideVariable]);

  const sorted = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...filtered].sort((a, b) => {
      if (sortBy === 'name') {
        return dir * (a.name ?? a.id).localeCompare(b.name ?? b.id);
      }
      if (sortBy === 'context') {
        return dir * ((a.context_length ?? 0) - (b.context_length ?? 0));
      }
      if (sortBy === 'prompt') {
        const av = a.pricing_prompt_per_mtok ?? Number.POSITIVE_INFINITY;
        const bv = b.pricing_prompt_per_mtok ?? Number.POSITIVE_INFINITY;
        return dir * (av - bv);
      }
      if (sortBy === 'completion') {
        const av = a.pricing_completion_per_mtok ?? Number.POSITIVE_INFINITY;
        const bv = b.pricing_completion_per_mtok ?? Number.POSITIVE_INFINITY;
        return dir * (av - bv);
      }
      const at = (a.pricing_prompt_per_mtok ?? 9999) + (a.pricing_completion_per_mtok ?? 9999);
      const bt = (b.pricing_prompt_per_mtok ?? 9999) + (b.pricing_completion_per_mtok ?? 9999);
      return dir * (at - bt);
    });
  }, [filtered, sortBy, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortBy === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir(key === 'name' ? 'asc' : 'asc');
    }
  };

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className="openrouter-modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="openrouter-modal" role="dialog" aria-modal="true">
        <div className="openrouter-modal__pattern" />
        <div className="openrouter-modal__header">
          <div>
            <h2 className="font-display text-headline-lg text-primary mb-1">
              Catálogo Completo
            </h2>
            <p className="text-sm text-on-surface-variant">
              {filtered.length} de {total} modelos · todos los proveedores de OpenRouter
            </p>
          </div>
          <button
            type="button"
            className="openrouter-modal__close"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="openrouter-modal__filters">
          <div className="openrouter-modal__search">
            <span className="material-symbols-outlined text-[18px] openrouter-modal__search-icon">
              search
            </span>
            <input
              type="text"
              placeholder="Buscar ID, nombre o proveedor..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
          </div>
          <select
            className="openrouter-modal__select"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            <option value="all">Todos los proveedores ({providers.length})</option>
            {providers.map((p) => (
              <option key={p} value={p}>
                {PROVIDER_LABELS[p] ?? p}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setOnlyFree((v) => !v)}
            className={`openrouter-modal__chip ${
              onlyFree ? 'openrouter-modal__chip--active' : ''
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">
              {onlyFree ? 'check' : 'paid'}
            </span>
            Solo gratis
          </button>
          <button
            type="button"
            onClick={() => setOnlyText((v) => !v)}
            className={`openrouter-modal__chip ${
              onlyText ? 'openrouter-modal__chip--active' : ''
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">
              {onlyText ? 'check' : 'text_fields'}
            </span>
            Solo texto
          </button>
          <button
            type="button"
            onClick={() => setHideVariable((v) => !v)}
            className={`openrouter-modal__chip ${
              hideVariable ? 'openrouter-modal__chip--active' : ''
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">
              {hideVariable ? 'check' : 'block'}
            </span>
            Ocultar precio variable
          </button>
          {(search || provider !== 'all' || onlyFree || onlyText || hideVariable) && (
            <button
              type="button"
              onClick={() => {
                setSearch('');
                setProvider('all');
                setOnlyFree(false);
                setOnlyText(false);
                setHideVariable(false);
              }}
              className="openrouter-modal__chip"
            >
              <span className="material-symbols-outlined text-[14px]">clear_all</span>
              Limpiar
            </button>
          )}
        </div>

        <div className="openrouter-modal__body">
          <table className="openrouter-modal__table">
            <thead>
              <tr>
                <th
                  onClick={() => toggleSort('name')}
                  className={sortBy === 'name' ? 'openrouter-modal__table-th--active' : ''}
                >
                  ID / Nombre {sortBy === 'name' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th
                  onClick={() => toggleSort('prompt')}
                  className={`text-right ${sortBy === 'prompt' ? 'openrouter-modal__table-th--active' : ''}`}
                >
                  Prompt $/M {sortBy === 'prompt' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th
                  onClick={() => toggleSort('completion')}
                  className={`text-right ${sortBy === 'completion' ? 'openrouter-modal__table-th--active' : ''}`}
                >
                  Compl. $/M {sortBy === 'completion' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th
                  onClick={() => toggleSort('total')}
                  className={`text-right ${sortBy === 'total' ? 'openrouter-modal__table-th--active' : ''}`}
                >
                  Total $/M {sortBy === 'total' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th
                  onClick={() => toggleSort('context')}
                  className={sortBy === 'context' ? 'openrouter-modal__table-th--active' : ''}
                >
                  Contexto {sortBy === 'context' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th>Modalidades</th>
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-on-surface-variant text-sm">
                    Sin resultados con esos filtros
                  </td>
                </tr>
              ) : (
                sorted.map((m, idx) => {
                  const p = m.pricing_prompt_per_mtok;
                  const c = m.pricing_completion_per_mtok;
                  const isFree = p === 0 && c === 0;
                  const isVar = (p != null && p < 0) || (c != null && c < 0);
                  const totalPrice =
                    p != null && c != null && p >= 0 && c >= 0 ? p + c : null;
                  const provLabel =
                    PROVIDER_LABELS[getProvider(m.id)] ?? getProvider(m.id);
                  const mods = m.modalities ?? [];
                  return (
                    <tr
                      key={m.id}
                      className="animate-openrouter-row-fade cursor-pointer"
                      style={{ animationDelay: `${Math.min(idx * 8, 400)}ms` }}
                      onClick={() => onSelectModel?.(m)}
                    >
                      <td>
                        <div className="flex flex-col">
                          <span className="font-semibold text-sm text-secondary truncate">
                            {m.name || m.id.split('/').pop()}
                          </span>
                          <span className="text-[10px] text-on-surface-variant truncate">
                            {m.id} · {provLabel}
                          </span>
                        </div>
                      </td>
                      <td
                        className={`openrouter-modal__price ${
                          isFree ? 'openrouter-modal__price--free' : ''
                        } ${isVar && (p ?? 0) < 0 ? 'openrouter-modal__price--variable' : ''}`}
                      >
                        {formatPrice(p)}
                      </td>
                      <td
                        className={`openrouter-modal__price ${
                          isFree ? 'openrouter-modal__price--free' : ''
                        } ${isVar && (c ?? 0) < 0 ? 'openrouter-modal__price--variable' : ''}`}
                      >
                        {formatPrice(c)}
                      </td>
                      <td className="openrouter-modal__price font-bold">
                        {totalPrice == null
                          ? isVar
                            ? 'Variable'
                            : '—'
                          : totalPrice === 0
                            ? 'Gratis'
                            : `$${totalPrice.toFixed(totalPrice < 0.01 ? 4 : 2)}`}
                      </td>
                      <td className="text-sm">{formatContext(m.context_length)}</td>
                      <td>
                        <div className="flex gap-1 flex-wrap">
                          {mods.length === 0 ? (
                            <span className="openrouter-modal__badge">TEXT</span>
                          ) : (
                            mods.slice(0, 4).map((mod) => (
                              <span
                                key={mod}
                                className={`openrouter-modal__badge ${
                                  mod === 'image' || mod === 'vision'
                                    ? 'openrouter-modal__badge--vision'
                                    : mod === 'audio'
                                      ? 'openrouter-modal__badge--audio'
                                      : ''
                                }`}
                              >
                                {mod.toUpperCase()}
                              </span>
                            ))
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="openrouter-modal__footer">
          <span>
            Click en encabezados para ordenar · Esc o click afuera para cerrar
          </span>
          <span>
            Mostrando <strong>{sorted.length}</strong> modelos
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
