import { BotStatus } from '@/types';
import LatencyChart from './LatencyChart';

interface SystemStatusProps {
  status: BotStatus | null;
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${days}d ${hours}h ${mins}m`;
}

function classifyLatency(ms: number): string {
  if (ms < 50) return 'Excelente';
  if (ms < 100) return 'Buena';
  if (ms < 200) return 'Regular';
  return 'Lenta';
}

export default function SystemStatus({ status }: SystemStatusProps) {
  const isOnline = status?.online ?? false;
  // Derive a safe numeric latency: fallback to 0 if missing/null/NaN
  const latencyValue =
    status != null &&
    status.latency_ms != null &&
    Number.isFinite(status.latency_ms)
      ? status.latency_ms
      : null;

  return (
    <section aria-label="System status" className="flex flex-col h-full gap-4 lg:gap-6 pb-4">
      {/* Hero Status Section */}
      <section className="grid grid-cols-12 gap-4 lg:gap-6">
        <div className="col-span-12 lg:col-span-8">
          <div className="bg-surface/40 backdrop-blur-md rounded-xl p-6 md:p-8 border border-white/40 shadow-[0px_10px_30px_rgba(168,0,33,0.03)] relative overflow-hidden h-full flex flex-col justify-center">
            <div className="absolute bottom-0 right-0 asanoha-pattern w-48 h-48"></div>
            <div className="flex items-center gap-4 md:gap-6 mb-3 md:mb-4">
              {/* Online Status Badge */}
              {status === null ? (
                <span className="font-body-md text-tertiary italic">Cargando estado...</span>
              ) : (
                <div className="relative">
                  <div
                    className={
                      'absolute inset-0 blur-xl rounded-full ' +
                      (isOnline ? 'bg-green-500/20' : 'bg-red-500/20')
                    }
                  ></div>
                  <div
                    className={
                      'relative flex items-center gap-3 backdrop-blur px-8 py-4 rounded-full border shadow-sm ' +
                      (isOnline
                        ? 'bg-white/60 border-green-200'
                        : 'bg-white/60 border-red-200')
                    }
                  >
                    <span
                      className={
                        'w-4 h-4 rounded-full ' +
                        (isOnline ? 'bg-green-500 animate-pulse' : 'bg-red-500')
                      }
                    ></span>
                    <span
                      className={
                        'font-headline-md tracking-wide ' +
                        (isOnline ? 'text-green-700' : 'text-red-700')
                      }
                    >
                      {isOnline ? 'En línea' : 'Fuera de línea'}
                    </span>
                  </div>
                </div>
              )}
            </div>
            <h3 className="font-display text-display text-primary mt-4 mb-2">
              Núcleo Operativo
            </h3>
            <p className="font-body-lg text-on-surface-variant max-w-xl">
              El bot está procesando comandos y eventos con normalidad. La latencia del
              santuario digital se mantiene en niveles óptimos.
            </p>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4">
          <div className="bg-primary-container/20 backdrop-blur-md rounded-xl p-6 border border-primary-fixed-dim/30 h-full flex flex-col items-center justify-center text-center">
            <span
              className="material-symbols-outlined text-secondary text-5xl mb-4"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              history
            </span>
            <h4 className="font-label-sm text-label-sm text-primary uppercase tracking-[0.2em] mb-1">
              Tiempo de Actividad
            </h4>
            <p className="font-headline-lg text-headline-lg text-primary tracking-tighter">
              {status ? formatUptime(status.uptime_seconds) : '--d --h --m'}
            </p>
            {status && (
              <>
                <div className="mt-6 w-full h-1 bg-outline-variant/30 rounded-full overflow-hidden">
                  <div
                    className="bg-secondary h-full transition-all duration-1000"
                    style={{
                      width: isOnline ? '100%' : '0%',
                      boxShadow: isOnline ? '0 0 10px rgba(183, 19, 41, 0.4)' : 'none',
                    }}
                  ></div>
                </div>
                <p className="mt-2 font-label-sm text-label-sm text-tertiary">
                  {isOnline ? '100% Disponibilidad' : '0% Disponibilidad'}
                </p>
              </>
            )}
            {!status && (
              <p className="mt-2 font-label-sm text-label-sm text-tertiary italic">Cargando...</p>
            )}
          </div>
        </div>
      </section>

      {/* Detailed Metrics Bento Grid */}
      <section className="grid grid-cols-12 gap-4 lg:gap-6">
        {/* Cogs Metric */}
        <div className="col-span-12 md:col-span-6 lg:col-span-4 group">
          <div className="bg-surface/60 backdrop-blur-lg rounded-xl p-5 md:p-6 border border-white/50 hover:border-secondary/30 transition-all duration-500 shadow-sm hover:shadow-lg relative overflow-hidden active:scale-[0.99] flex flex-col h-full">
            <div className="absolute -right-4 -top-4 opacity-5 group-hover:opacity-10 transition-opacity">
              <span className="material-symbols-outlined text-9xl">settings</span>
            </div>
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 bg-secondary/10 rounded-lg">
                <span className="material-symbols-outlined text-secondary">extension</span>
              </div>
              <span className="text-tertiary font-label-sm uppercase">Cogs</span>
            </div>
            <p className="font-headline-lg text-headline-lg text-on-surface mb-2">
              {status ? `${status.loaded_cogs.length} Cargados` : '-- Cargados'}
            </p>
            <p className="font-body-md text-tertiary">
              Módulos funcionales activos en el entorno actual.
            </p>
            <div className="mt-4 md:mt-auto flex gap-2">
              {status && status.loaded_cogs.length > 0
                ? status.loaded_cogs.slice(0, 3).map((cog) => (
                    <span
                      key={cog}
                      className="px-3 py-1 bg-primary-container/40 text-on-primary-container text-xs rounded-full font-bold"
                    >
                      {cog}
                    </span>
                  ))
                : ['Admin', 'Social', 'Games'].map((tag) => (
                    <span
                      key={tag}
                      className="px-3 py-1 bg-primary-container/40 text-on-primary-container text-xs rounded-full font-bold"
                    >
                      {tag}
                    </span>
                  ))}
            </div>
          </div>
        </div>

        {/* WS Clients Metric */}
        <div className="col-span-12 md:col-span-6 lg:col-span-4 group">
          <div className="bg-surface/60 backdrop-blur-lg rounded-xl p-5 md:p-6 border border-white/50 hover:border-secondary/30 transition-all duration-500 shadow-sm hover:shadow-lg relative overflow-hidden active:scale-[0.99] flex flex-col h-full">
            <div className="absolute -right-4 -top-4 opacity-5 group-hover:opacity-10 transition-opacity">
              <span className="material-symbols-outlined text-9xl">hub</span>
            </div>
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 bg-primary/10 rounded-lg">
                <span className="material-symbols-outlined text-primary">router</span>
              </div>
              <span className="text-tertiary font-label-sm uppercase">WebSocket</span>
            </div>
            <p className="font-headline-lg text-headline-lg text-on-surface mb-2">
              {status ? `${status.connected_ws_clients} Clientes WS` : '-- Clientes WS'}
            </p>
            <p className="font-body-md text-tertiary">
              Conexiones activas de puerta de enlace en tiempo real.
            </p>
            <div className="mt-4 md:mt-auto flex items-center gap-2 text-green-600 font-label-sm">
              <span className="material-symbols-outlined text-sm">trending_up</span>
              <span>Tráfico Estable</span>
            </div>
          </div>
        </div>

        {/* Latency / Health Chart */}
        <div className="col-span-12 lg:col-span-4 group">
          <div className="bg-surface/60 backdrop-blur-lg rounded-xl p-5 md:p-6 border border-white/50 hover:border-secondary/30 transition-all duration-500 shadow-sm hover:shadow-lg flex flex-col h-full active:scale-[0.99]">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 bg-tertiary-container/30 rounded-lg">
                <span className="material-symbols-outlined text-tertiary">bolt</span>
              </div>
              <span className="text-tertiary font-label-sm uppercase">Latencia</span>
            </div>
            <div className="flex-grow w-full relative h-16 md:h-20 mb-4 overflow-hidden rounded-md flex items-end">
              <LatencyChart latencyMs={latencyValue} />
            </div>
            <div className="flex justify-between items-center">
              <span className="font-headline-md text-primary">
                {latencyValue != null ? `${Math.round(latencyValue)}ms` : '--ms'}
              </span>
              <span className="font-label-sm text-tertiary italic">
                {latencyValue != null ? classifyLatency(latencyValue) : ''}
              </span>
            </div>
          </div>
        </div>

        {/* Secondary Visual Card */}
        <div className="col-span-12">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:gap-6 mt-4 lg:mt-0">
            <div className="md:col-span-2 relative h-48 rounded-xl overflow-hidden border border-outline-variant/30">
              <img
                alt="Digital Zen Garden"
                className="w-full h-full object-cover grayscale-[0.2] opacity-80"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuChvMvpZu50Lusz1V6vx85jclnlp-AbVm1JspCMpl5iwKTx60jlptLwCuSZY82iY-haekJJeu4I7r49qfmKPu7webhQ5Lpa0ys6oz0Yc91slGUv9XbnRHUTK9Qo6VmEttW9SFjQ13ioZpETj1qNPrzpDySJQIyD5KYTiaCbtPdeAkkVaC5D-ilQgR_83r53tN_DqiO9KeTDCIdxIh4PY2fE_kJ9kQIouTnpfxqpI64ji-e85T9Ab_3G2RhO0FqEikbfDviOu4u-944"
              />
              <div className="absolute inset-0 bg-gradient-to-r from-surface via-transparent to-transparent flex items-center p-6 md:p-8">
                <div className="max-w-xs">
                  <h5 className="font-headline-md text-primary mb-2">Sincronización</h5>
                  <p className="font-body-md text-on-surface-variant">
                    Todos los sistemas secundarios se encuentran en armonía con el servidor
                    principal.
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-secondary p-6 md:p-8 rounded-xl flex flex-col justify-between text-on-secondary h-48">
              <div>
                <span className="material-symbols-outlined text-4xl mb-4">memory</span>
                <h6 className="font-headline-md mb-2">Memoria</h6>
              </div>
              <div>
                <div className="text-4xl font-headline-lg mb-1">
                  {status ? `${status.memory_mb.toFixed(1)}MB` : '--MB'}
                </div>
                <p className="text-on-secondary/70 font-label-sm">Uso de Memoria RAM</p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </section>
  );
}

