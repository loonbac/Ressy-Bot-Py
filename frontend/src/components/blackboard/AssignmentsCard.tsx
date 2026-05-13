import type { BlackboardAssignment } from '@/api/blackboard';
import './AssignmentsCard.css';
import './animations.css';

interface Props {
  assignments: BlackboardAssignment[];
  loading: boolean;
  onRefresh: () => void;
}

function formatDate(iso: string | null): string {
  if (!iso) return 'Sin fecha';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString('es-PE', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function statusClass(status: string): string {
  const s = status.toLowerCase();
  if (s.includes('entregad') || s.includes('done') || s.includes('completed')) return 'is-done';
  if (s.includes('vencid') || s.includes('late') || s.includes('overdue')) return 'is-late';
  return '';
}

export default function AssignmentsCard({ assignments, loading, onRefresh }: Props) {
  return (
    <div className="bb-assignments-card rounded-2xl p-5 shadow-[0px_10px_30px_rgba(168,0,33,0.04)] h-full flex flex-col min-h-0 overflow-hidden">
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-secondary text-[22px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            assignment
          </span>
          <span className="font-headline-md text-headline-md text-primary leading-none">
            Tareas Scrapeadas
          </span>
          <span className="text-label-sm text-tertiary ml-2 px-2 py-0.5 rounded-full bg-surface-container-highest">
            {assignments.length}
          </span>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="text-label-sm text-tertiary hover:text-secondary transition-colors flex items-center gap-1 disabled:opacity-50"
          title="Refrescar lista"
        >
          <span
            className={`material-symbols-outlined text-[18px] ${loading ? 'animate-spin' : ''}`}
          >
            refresh
          </span>
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-2">
        {assignments.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center text-center py-10 text-tertiary">
            <span className="material-symbols-outlined text-4xl mb-2 opacity-50">
              inbox
            </span>
            <p className="text-sm">No hay tareas todavía</p>
            <p className="text-[11px] opacity-70 mt-1">
              Ejecutá el scraper para sincronizar
            </p>
          </div>
        )}
        {assignments.map((a, idx) => (
          <div
            key={a.id}
            className="bb-assignments-card__row animate-bb-row-enter rounded-lg p-3"
            style={{ animationDelay: `${Math.min(idx * 0.03, 0.3)}s` }}
          >
            <div className="flex items-start justify-between gap-2 mb-1">
              <a
                href={a.source_url || '#'}
                target="_blank"
                rel="noreferrer"
                className="text-sm font-bold text-on-surface hover:text-secondary transition-colors line-clamp-2 flex-1"
              >
                {a.title}
              </a>
              <span
                className={`bb-assignments-card__status ${statusClass(a.status)} text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full flex-shrink-0`}
              >
                {a.status}
              </span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-tertiary">
              <span className="truncate flex items-center gap-1 max-w-[60%]">
                <span className="material-symbols-outlined text-[13px]">school</span>
                {a.course_name}
              </span>
              <span className="flex items-center gap-1 flex-shrink-0">
                <span className="material-symbols-outlined text-[13px]">event</span>
                {formatDate(a.due_date)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
