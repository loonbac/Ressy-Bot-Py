import './ExecutionsList.css';
import { SUPPORTED_LANGUAGES, type CodeRunnerExecution } from '@/api/code-runner';

interface Props {
  executions: CodeRunnerExecution[];
}

function langShort(lang: string): string {
  const found = SUPPORTED_LANGUAGES.find((l) => l.id === lang.toLowerCase());
  return found?.short ?? lang.slice(0, 3).toUpperCase();
}

function relTime(ts: number): string {
  const diff = Date.now() / 1000 - ts;
  const abs = Math.abs(diff);
  if (abs < 60) return 'Hace segs';
  const mins = Math.floor(abs / 60);
  if (mins < 60) return `Hace ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `Hace ${hours}h`;
  return `Hace ${Math.floor(hours / 24)}d`;
}

function statusBadge(status: string): { label: string; cls: string } {
  if (status === 'success') return { label: 'Éxito', cls: 'cr-exec-badge--ok' };
  if (status === 'error') return { label: 'Error', cls: 'cr-exec-badge--err' };
  if (status === 'blocked') return { label: 'Bloqueado', cls: 'cr-exec-badge--err' };
  if (status === 'rate_limited') return { label: 'Rate Limit', cls: 'cr-exec-badge--warn' };
  return { label: status, cls: 'cr-exec-badge--neutral' };
}

function severityBadge(security: CodeRunnerExecution['security']): { label: string; icon: string; cls: string } {
  const sev = security?.severity ?? 'low';
  if (security?.malicious) return { label: 'Severo', icon: 'warning', cls: 'cr-exec-sec--err' };
  if (sev === 'high' || sev === 'critical') return { label: sev, icon: 'warning', cls: 'cr-exec-sec--err' };
  if (sev === 'medium') return { label: 'Medio', icon: 'shield', cls: 'cr-exec-sec--warn' };
  return { label: 'Limpio', icon: 'verified_user', cls: 'cr-exec-sec--ok' };
}

export default function ExecutionsList({ executions }: Props) {
  return (
    <div className="cr-card cr-executions-card animate-cr-card-enter animate-cr-stagger-6">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <span className="cr-card__icon material-symbols-outlined">data_object</span>
          <h3 className="font-headline-md text-headline-md text-primary">Últimas ejecuciones</h3>
        </div>
        <span className="text-[11px] text-on-surface-variant">{executions.length} mostradas</span>
      </div>

      {executions.length === 0 ? (
        <div className="text-center py-8 text-on-surface-variant text-sm italic">
          Sin ejecuciones registradas. Cuando un usuario corra <code>/ejecutar</code> aparecerán aquí.
        </div>
      ) : (
        <div className="space-y-2.5">
          {executions.map((ex, idx) => {
            const badge = statusBadge(ex.status);
            const sec = severityBadge(ex.security);
            return (
              <div
                key={ex.id}
                className="cr-executions-card__row animate-cr-row-fade"
                style={{ animationDelay: `${idx * 25}ms` }}
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="cr-executions-card__lang">
                    <span>{langShort(ex.language)}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">
                      {ex.analysis?.purpose || `Snippet ${ex.language}`}
                    </p>
                    <p className="text-[11px] text-on-surface-variant">
                      <span className="font-mono">{ex.user_id.slice(-6)}</span> · {relTime(ex.created_at)}
                      {ex.session_id ? ` · sesión #${ex.session_id}` : ''}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-4 flex-shrink-0">
                  <div className="text-center hidden sm:block">
                    <p className="text-[9px] text-on-surface-variant uppercase font-bold tracking-wider">
                      Seguridad
                    </p>
                    <span className={`cr-exec-sec ${sec.cls}`}>
                      <span className="material-symbols-outlined text-[14px]">{sec.icon}</span>
                      {sec.label}
                    </span>
                  </div>
                  <span className={`cr-exec-badge ${badge.cls}`}>{badge.label}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
