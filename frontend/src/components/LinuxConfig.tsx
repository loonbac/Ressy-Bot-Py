import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchLinuxConfig,
  fetchLinuxDiscordChannels,
  fetchLinuxProduct,
  fetchLinuxProducts,
  fetchLinuxSummary,
  refreshLinuxNow,
  updateLinuxConfig,
  type LinuxConfig as LinuxConfigType,
  type LinuxDiscordChannel,
  type LinuxProduct,
  type LinuxProductDetail,
  type LinuxRefreshResult,
  type LinuxSummary,
} from '@/api/linux';
import PageHeader from './linux/PageHeader';
import StatusBarCard from './linux/StatusBarCard';
import DistributionsGrid from './linux/DistributionsGrid';
import TimelineCard from './linux/TimelineCard';
import QuickConfigCard from './linux/QuickConfigCard';
import SettingsPanelCard, { type ActivityEntry } from './linux/SettingsPanelCard';
import FooterActions, { type SaveState } from './linux/FooterActions';
import './linux/animations.css';

interface Feedback {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

interface Props {
  onNavigate?: (section: string) => void;
}

const POLL_INTERVAL_MS = 30_000;
const MAX_ACTIVITY = 12;

function humanizeNow(): string {
  const now = new Date();
  return now.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });
}

function formatLastSync(products: LinuxProduct[]): string {
  const stamps = products
    .map((p) => p.last_check_at)
    .filter((t): t is number => typeof t === 'number');
  if (stamps.length === 0) return 'Nunca';
  const newest = Math.max(...stamps);
  const diff = Date.now() / 1000 - newest;
  if (diff < 60) return 'hace unos segundos';
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`;
  return `hace ${Math.floor(diff / 86400)} d`;
}

export default function LinuxConfig({ onNavigate }: Props) {
  const [products, setProducts] = useState<LinuxProduct[]>([]);
  const [summary, setSummary] = useState<LinuxSummary | null>(null);
  const [details, setDetails] = useState<Record<string, LinuxProductDetail>>({});
  const [config, setConfig] = useState<LinuxConfigType | null>(null);
  const [originalConfig, setOriginalConfig] = useState<LinuxConfigType | null>(null);
  const [channels, setChannels] = useState<LinuxDiscordChannel[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<LinuxRefreshResult | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [testing, setTesting] = useState(false);
  const [testFeedback, setTestFeedback] = useState<'idle' | 'success' | 'error'>('idle');
  const [activity, setActivity] = useState<ActivityEntry[]>([]);

  const detailsRef = useRef(details);
  detailsRef.current = details;

  const pushActivity = useCallback((entry: Omit<ActivityEntry, 'id' | 'date'>) => {
    setActivity((prev) =>
      [
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          date: humanizeNow(),
          ...entry,
        },
        ...prev,
      ].slice(0, MAX_ACTIVITY),
    );
  }, []);

  const loadDetails = useCallback(async (slugs: string[]) => {
    try {
      const results = await Promise.all(
        slugs.map((slug) =>
          fetchLinuxProduct(slug).then(
            (d) => [slug, d] as const,
            () => [slug, null] as const,
          ),
        ),
      );
      const merged: Record<string, LinuxProductDetail> = { ...detailsRef.current };
      for (const [slug, detail] of results) {
        if (detail) merged[slug] = detail;
      }
      setDetails(merged);
    } catch {
      /* ignore — partial failures already filtered */
    }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [prods, summ, cfg, chs] = await Promise.all([
        fetchLinuxProducts(),
        fetchLinuxSummary(),
        fetchLinuxConfig(),
        fetchLinuxDiscordChannels().catch(() => [] as LinuxDiscordChannel[]),
      ]);
      setProducts(prods);
      setSummary(summ);
      setConfig(cfg);
      setOriginalConfig(cfg);
      setChannels(chs);
      if (prods.length > 0) {
        setSelectedSlug((curr) => curr ?? prods[0].slug);
        await loadDetails(prods.map((p) => p.slug));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar datos');
    } finally {
      setLoading(false);
    }
  }, [loadDetails]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Poll products + summary every 30s — pause when tab hidden
  useEffect(() => {
    let cancelled = false;
    let timerId: number | null = null;

    const poll = async () => {
      try {
        const [prods, summ] = await Promise.all([fetchLinuxProducts(), fetchLinuxSummary()]);
        if (cancelled) return;
        setProducts(prods);
        setSummary(summ);
      } catch {
        /* ignore polling errors */
      }
    };

    const start = () => {
      if (timerId !== null) return;
      timerId = window.setInterval(poll, POLL_INTERVAL_MS);
    };
    const stop = () => {
      if (timerId !== null) {
        window.clearInterval(timerId);
        timerId = null;
      }
    };
    const handleVisibility = () => {
      if (document.hidden) stop();
      else start();
    };

    if (!document.hidden) start();
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      cancelled = true;
      stop();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  const updateField = useCallback(
    <K extends keyof LinuxConfigType>(key: K, value: LinuxConfigType[K]) => {
      setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
    },
    [],
  );

  const showFeedback = useCallback((kind: 'success' | 'error', text: string) => {
    setFeedback({ kind, text, nonce: Date.now() });
    window.setTimeout(() => {
      setFeedback((prev) => (prev && prev.text === text ? null : prev));
    }, 4200);
  }, []);

  const dirty = useMemo(() => {
    if (!config || !originalConfig) return false;
    return JSON.stringify(config) !== JSON.stringify(originalConfig);
  }, [config, originalConfig]);

  const handleSave = useCallback(async () => {
    if (!config) return;
    setSaveState('saving');
    try {
      const updated = await updateLinuxConfig(config);
      setConfig(updated);
      setOriginalConfig(updated);
      setSaveState('success');
      showFeedback('success', 'Configuración guardada');
      pushActivity({ event: 'Configuración actualizada', status: 'ok' });
      window.setTimeout(() => setSaveState('idle'), 1800);
    } catch (err) {
      setSaveState('error');
      const msg = err instanceof Error ? err.message : 'Error al guardar';
      showFeedback('error', msg);
      pushActivity({ event: `Error al guardar: ${msg}`, status: 'error' });
      window.setTimeout(() => setSaveState('idle'), 1800);
    }
  }, [config, pushActivity, showFeedback]);

  const handleDiscard = useCallback(() => {
    if (originalConfig) {
      setConfig(originalConfig);
      showFeedback('success', 'Cambios descartados');
    }
  }, [originalConfig, showFeedback]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const result = await refreshLinuxNow();
      setLastRefresh(result);
      if (result.skipped) {
        showFeedback('error', 'Scheduler pausado — activa el plugin antes de refrescar.');
        pushActivity({ event: 'Refresh ignorado (plugin pausado)', status: 'error' });
      } else {
        showFeedback(
          'success',
          `Refresh completado: ${result.refreshed} ok · ${result.failed} error`,
        );
        pushActivity({
          event: `Sync manual: ${result.refreshed} ok · ${result.failed} error`,
          status: result.failed > 0 ? 'error' : 'ok',
        });
      }
      const [prods, summ] = await Promise.all([fetchLinuxProducts(), fetchLinuxSummary()]);
      setProducts(prods);
      setSummary(summ);
      await loadDetails(prods.map((p) => p.slug));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error al refrescar';
      showFeedback('error', msg);
      pushActivity({ event: `Refresh fallido: ${msg}`, status: 'error' });
    } finally {
      setRefreshing(false);
    }
  }, [loadDetails, pushActivity, showFeedback]);

  const handleSendTest = useCallback(async () => {
    setTesting(true);
    setTestFeedback('idle');
    try {
      await refreshLinuxNow();
      setTestFeedback('success');
      pushActivity({ event: 'Refresh manual disparado desde panel rápido', status: 'sent' });
      window.setTimeout(() => setTestFeedback('idle'), 1800);
    } catch (err) {
      setTestFeedback('error');
      const msg = err instanceof Error ? err.message : 'Error al disparar';
      showFeedback('error', msg);
      window.setTimeout(() => setTestFeedback('idle'), 1800);
    } finally {
      setTesting(false);
    }
  }, [pushActivity, showFeedback]);

  const scrollToSettings = useCallback(() => {
    const el = document.getElementById('linux-settings-panel');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  const lastSync = useMemo(() => formatLastSync(products), [products]);

  if (loading) {
    return (
      <section className="fixed top-20 bottom-0 left-64 right-0 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl text-secondary animate-linux-sync-spin">
            progress_activity
          </span>
          <p className="text-on-surface-variant font-body-md">
            Cargando distribuciones Linux...
          </p>
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
          <button
            onClick={loadAll}
            className="bg-secondary text-white px-6 py-2 rounded-lg font-label-sm"
          >
            Reintentar
          </button>
        </div>
      </section>
    );
  }

  if (!config) return null;

  return (
    <section
      aria-label="Configuración de Linux Updates"
      className="fixed top-20 bottom-0 left-64 right-0 px-margin-desktop py-4 overflow-y-auto"
    >
      <div className="max-w-container-max mx-auto flex flex-col gap-5 pb-8">
        <div className="flex items-center justify-between gap-3">
          <PageHeader onBack={() => onNavigate?.('plugins')} />
        </div>

        {error && (
          <div className="p-2.5 bg-error-container/50 border border-error/20 rounded-lg flex items-center gap-3 text-error animate-linux-error-shake">
            <span className="material-symbols-outlined text-[18px]">error</span>
            <span className="font-body-md text-sm">{error}</span>
          </div>
        )}

        <StatusBarCard
          products={products}
          summary={summary}
          lastSync={lastSync}
          refreshing={refreshing}
          onRefresh={handleRefresh}
          onScrollToSettings={scrollToSettings}
        />

        <DistributionsGrid
          products={products}
          details={details}
          selectedSlug={selectedSlug}
          onSelect={(slug) => setSelectedSlug(slug)}
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-stretch lg:h-[520px]">
          <div className="lg:col-span-2 min-h-0 flex flex-col">
            <TimelineCard
              products={products}
              details={details}
              selectedSlug={selectedSlug}
              onSelect={setSelectedSlug}
            />
          </div>
          <div className="min-h-0 flex flex-col">
            <QuickConfigCard
              config={config}
              onChange={updateField}
              onSendTest={handleSendTest}
              testing={testing}
              testFeedback={testFeedback}
            />
          </div>
        </div>

        <SettingsPanelCard
          config={config}
          channels={channels}
          onChange={updateField}
          activity={activity}
          lastRefresh={lastRefresh}
        />

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
