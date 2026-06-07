import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  addVideoWorker,
  deleteVideoWorker,
  fetchVideoConfig,
  fetchVideoStatus,
  fetchVideoWorkers,
  stopVideoWorker,
  updateVideoConfig,
  type VideoConfig as VideoConfigType,
  type VideoManagerStatus,
  type VideoWorker,
} from '@/api/videos';
import PageHeader from './videos/PageHeader';
import StatusCard from './videos/StatusCard';
import WorkersCard from './videos/WorkersCard';
import PlaybackSettingsCard from './videos/PlaybackSettingsCard';
import CommandsCard from './videos/CommandsCard';
import FooterActions, { type Feedback, type SaveState } from './videos/FooterActions';
import './videos/animations.css';

interface Props {
  onNavigate?: (section: string) => void;
}

const POLL_INTERVAL_MS = 4000;

export default function VideosConfig({ onNavigate }: Props) {
  const [config, setConfig] = useState<VideoConfigType | null>(null);
  const [originalConfig, setOriginalConfig] = useState<VideoConfigType | null>(null);
  const [workers, setWorkers] = useState<VideoWorker[]>([]);
  const [managerOnline, setManagerOnline] = useState(false);
  const [status, setStatus] = useState<VideoManagerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const mounted = useRef(true);

  const showFeedback = useCallback((kind: 'success' | 'error', text: string) => {
    setFeedback({ kind, text, nonce: Date.now() });
    window.setTimeout(() => {
      setFeedback((prev) => (prev && prev.text === text ? null : prev));
    }, 4200);
  }, []);

  const refreshLive = useCallback(async () => {
    try {
      const [w, st] = await Promise.all([fetchVideoWorkers(), fetchVideoStatus()]);
      if (!mounted.current) return;
      setWorkers(w.workers);
      setManagerOnline(w.manager_online);
      setStatus(st);
    } catch {
      /* ignore polling errors */
    }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const cfg = await fetchVideoConfig();
      if (!mounted.current) return;
      setConfig(cfg);
      setOriginalConfig(cfg);
      await refreshLive();
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : 'Error al cargar datos');
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [refreshLive]);

  useEffect(() => {
    mounted.current = true;
    loadAll();
    return () => {
      mounted.current = false;
    };
  }, [loadAll]);

  // Poll live worker/status — pause when tab hidden.
  useEffect(() => {
    let timer: number | null = null;
    const start = () => {
      if (timer !== null) return;
      timer = window.setInterval(refreshLive, POLL_INTERVAL_MS);
    };
    const stop = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };
    const onVis = () => (document.hidden ? stop() : start());
    if (!document.hidden) start();
    document.addEventListener('visibilitychange', onVis);
    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [refreshLive]);

  const updateField = useCallback(
    <K extends keyof VideoConfigType>(key: K, value: VideoConfigType[K]) => {
      setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
    },
    [],
  );

  const dirty = useMemo(() => {
    if (!config || !originalConfig) return false;
    return JSON.stringify(config) !== JSON.stringify(originalConfig);
  }, [config, originalConfig]);

  const handleSave = async () => {
    if (!config) return;
    setSaveState('saving');
    try {
      const updated = await updateVideoConfig(config);
      setConfig(updated);
      setOriginalConfig(updated);
      setSaveState('success');
      showFeedback('success', 'Configuración guardada');
      window.setTimeout(() => setSaveState('idle'), 1800);
    } catch (err) {
      setSaveState('error');
      showFeedback('error', err instanceof Error ? err.message : 'Error al guardar');
      window.setTimeout(() => setSaveState('idle'), 1800);
    }
  };

  const handleDiscard = () => {
    if (originalConfig) {
      setConfig(originalConfig);
      showFeedback('success', 'Cambios descartados');
    }
  };

  const handleAddWorker = async (token: string) => {
    const w = await addVideoWorker(token);
    showFeedback('success', `Worker agregado: ${w.tag || w.username || w.user_id}`);
    await refreshLive();
  };

  const handleDeleteWorker = async (id: string) => {
    try {
      await deleteVideoWorker(id);
      showFeedback('success', 'Worker eliminado');
      await refreshLive();
    } catch (err) {
      showFeedback('error', err instanceof Error ? err.message : 'No se pudo eliminar');
      throw err;
    }
  };

  const handleStopWorker = async (id: string) => {
    try {
      await stopVideoWorker(id);
      showFeedback('success', 'Reproducción detenida');
      await refreshLive();
    } catch (err) {
      showFeedback('error', err instanceof Error ? err.message : 'No se pudo detener');
      throw err;
    }
  };

  if (loading) {
    return (
      <section className="fixed top-20 bottom-0 left-64 right-0 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl animate-videos-spin" style={{ color: '#ff0050' }}>
            progress_activity
          </span>
          <p className="text-on-surface-variant font-body-md">Cargando reproductor de videos…</p>
        </div>
      </section>
    );
  }

  if (error && !config) {
    return (
      <section className="fixed top-20 bottom-0 left-64 right-0 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-error">
          <span className="material-symbols-outlined text-4xl">error</span>
          <p className="font-body-md">{error}</p>
          <button onClick={loadAll} className="videos-btn-primary px-6 py-2">
            Reintentar
          </button>
        </div>
      </section>
    );
  }

  if (!config) return null;

  return (
    <section
      aria-label="Configuración de Videos"
      className="fixed top-20 bottom-0 left-64 right-0 px-margin-desktop py-4 overflow-hidden"
    >
      <div className="max-w-container-max mx-auto h-full grid grid-rows-[auto_minmax(0,1fr)_auto] gap-3 overflow-hidden">
        <PageHeader onBack={() => onNavigate?.('plugins')} />

        <div
          className="grid grid-cols-12 gap-3 min-h-0 overflow-hidden"
          style={{ gridTemplateRows: 'auto minmax(0, 1fr)' }}
        >
          {/* Top: manager status (full width, short) */}
          <div className="col-span-12 min-h-0">
            <StatusCard status={status} workerCount={workers.length} />
          </div>

          {/* Main: workers | quality | commands */}
          <div className="col-span-12 lg:col-span-5 min-h-0 overflow-hidden">
            <WorkersCard
              workers={workers}
              managerOnline={managerOnline}
              onAdd={handleAddWorker}
              onDelete={handleDeleteWorker}
              onStop={handleStopWorker}
            />
          </div>
          <div className="col-span-12 lg:col-span-4 min-h-0 overflow-hidden">
            <PlaybackSettingsCard config={config} onChange={updateField} />
          </div>
          <div className="col-span-12 lg:col-span-3 min-h-0 overflow-hidden">
            <CommandsCard config={config} onChange={updateField} />
          </div>
        </div>

        <FooterActions
          saveState={saveState}
          feedback={feedback}
          dirty={dirty}
          onSave={handleSave}
          onDiscard={handleDiscard}
        />
      </div>
    </section>
  );
}
