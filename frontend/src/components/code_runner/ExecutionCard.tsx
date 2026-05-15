import './ExecutionCard.css';
import { SUPPORTED_LANGUAGES, type CodeRunnerConfig, type CodeRunnerStatus } from '@/api/code-runner';

interface Props {
  config: CodeRunnerConfig;
  status: CodeRunnerStatus | null;
  onPatch: (patch: Partial<CodeRunnerConfig>) => void;
}

export default function ExecutionCard({ config, status, onPatch }: Props) {
  const enabledSet = new Set(config.allowed_languages.map((l) => l.toLowerCase()));

  const toggleLang = (id: string) => {
    const lower = id.toLowerCase();
    const next = new Set(enabledSet);
    if (next.has(lower)) next.delete(lower);
    else next.add(lower);
    onPatch({ allowed_languages: Array.from(next) });
  };

  return (
    <div className="cr-card cr-execution-card animate-cr-card-enter animate-cr-stagger-3 w-full flex flex-col">
      <div className="flex items-center gap-3 mb-5">
        <span className="cr-card__icon material-symbols-outlined">terminal</span>
        <div>
          <h3 className="font-headline-md text-headline-md text-primary">Ejecución</h3>
          <p className="text-[11px] text-on-surface-variant">
            Lenguajes permitidos, límites de tamaño y timeout del runner.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
        <div className="md:col-span-2">
          <label className="cr-label">Lenguajes permitidos</label>
          <div className="flex flex-wrap gap-2">
            {SUPPORTED_LANGUAGES.map((lang) => {
              const active = enabledSet.has(lang.id);
              return (
                <button
                  key={lang.id}
                  type="button"
                  onClick={() => toggleLang(lang.id)}
                  className={`cr-chip ${active ? 'cr-chip--active' : 'cr-chip--inactive'}`}
                  title={lang.label}
                >
                  <span className="font-mono">{lang.short}</span>
                  <span className="opacity-80">{lang.label}</span>
                </button>
              );
            })}
          </div>
          <p className="cr-hint">
            Solo los lenguajes activos se aceptan en <code>/ejecutar</code> y bloques triple backtick dentro de
            sesiones. Piston debe soportarlos en el endpoint configurado.
          </p>
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="cr-label">Máx. caracteres código</label>
            <span className="cr-slider-value">{config.max_code_chars.toLocaleString('es-PE')}</span>
          </div>
          <input
            type="range"
            min={500}
            max={20000}
            step={500}
            value={config.max_code_chars}
            onChange={(e) => onPatch({ max_code_chars: Number(e.target.value) })}
            className="cr-slider"
          />
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="cr-label">Máx. caracteres salida</label>
            <span className="cr-slider-value">{config.max_output_chars.toLocaleString('es-PE')}</span>
          </div>
          <input
            type="range"
            min={500}
            max={20000}
            step={500}
            value={config.max_output_chars}
            onChange={(e) => onPatch({ max_output_chars: Number(e.target.value) })}
            className="cr-slider"
          />
        </div>

        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="cr-label">Timeout ejecución (s)</label>
            <span className="cr-slider-value">{config.exec_timeout_seconds}s</span>
          </div>
          <input
            type="range"
            min={1}
            max={60}
            value={config.exec_timeout_seconds}
            onChange={(e) => onPatch({ exec_timeout_seconds: Number(e.target.value) })}
            className="cr-slider"
          />
        </div>

        <div>
          <label className="cr-label">Endpoint Piston</label>
          <input
            type="text"
            className="cr-input font-mono text-[12px]"
            value={config.piston_url}
            onChange={(e) => onPatch({ piston_url: e.target.value })}
            spellCheck={false}
          />
          <p className="cr-hint">URL del API público o self-host de Piston.</p>
        </div>
      </div>

      <div className="cr-execution-card__footer mt-auto">
        <div className="cr-execution-card__service">
          <div>
            <p className="cr-label !mb-0">Servicio</p>
            <p className="text-[11px] text-on-surface-variant mt-0.5">
              {status?.ready ? 'Operativo · backend respondiendo' : 'Sin respuesta del backend'}
            </p>
          </div>
          <span
            className={`material-symbols-outlined text-[24px] ${
              status?.ready ? 'text-emerald-500' : 'text-amber-500'
            }`}
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {status?.ready ? 'check_circle' : 'pending'}
          </span>
        </div>
      </div>
    </div>
  );
}
