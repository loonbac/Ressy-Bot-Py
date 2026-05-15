import { useCallback, useEffect, useState } from 'react';
import './openrouter/animations.css';
import PageHeader from './openrouter/PageHeader';
import StatusCard from './openrouter/StatusCard';
import ScrapeHealthCard from './openrouter/ScrapeHealthCard';
import PhasesGrid from './openrouter/PhasesGrid';
import ModelsTable from './openrouter/ModelsTable';
import DiscordPreviewCard from './openrouter/DiscordPreviewCard';
import AliasesDrawer from './openrouter/AliasesDrawer';
import RankingDrawer from './openrouter/RankingDrawer';
import WeightsEditor from './openrouter/WeightsEditor';
import ScrapeHistoryCard from './openrouter/ScrapeHistoryCard';
import BenchmarksCard from './openrouter/BenchmarksCard';
import ConfigCard from './openrouter/ConfigCard';
import ModelsModal from './openrouter/ModelsModal';
import {
  fetchOpenRouterStatus,
  fetchOpenRouterConfig,
  updateOpenRouterConfig,
  fetchOpenRouterModels,
  refreshOpenRouterCatalog,
  fetchPhases,
  fetchPhaseRanking,
  triggerScrape,
  fetchAliases,
  fetchScrapeRuns,
  fetchBenchmarks,
  fetchOpenRouterDiscordChannels,
  triggerRankingEmbed,
  type DiscordChannel,
  type OpenRouterStatus,
  type OpenRouterConfig as OpenRouterConfigType,
  type OpenRouterModel,
  type PhaseSummary,
  type RankingResponse,
  type AliasEntry,
  type ScrapeRun,
  type BenchmarkRow,
} from '@/api/openrouter';

interface Props {
  onNavigate?: (section: string) => void;
  botName?: string;
  botAvatarUrl?: string;
}

interface Toast {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

export default function OpenRouterConfig({ onNavigate, botName, botAvatarUrl }: Props) {
  const [status, setStatus] = useState<OpenRouterStatus | null>(null);
  const [config, setConfig] = useState<OpenRouterConfigType | null>(null);
  const [models, setModels] = useState<OpenRouterModel[]>([]);
  const [totalModels, setTotalModels] = useState(0);
  const [phases, setPhases] = useState<PhaseSummary[]>([]);
  const [rankings, setRankings] = useState<Record<string, RankingResponse | null>>({});
  const [aliases, setAliases] = useState<AliasEntry[]>([]);
  const [runs, setRuns] = useState<ScrapeRun[]>([]);
  const [benchmarks, setBenchmarks] = useState<BenchmarkRow[]>([]);
  const [channels, setChannels] = useState<DiscordChannel[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloading, setReloading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshState, setRefreshState] = useState<'idle' | 'loading' | 'success' | 'error'>(
    'idle',
  );
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [modalOpen, setModalOpen] = useState(false);
  const [aliasesOpen, setAliasesOpen] = useState(false);
  const [allModels, setAllModels] = useState<OpenRouterModel[]>([]);
  const [rankingDrawerPhase, setRankingDrawerPhase] = useState<PhaseSummary | null>(null);
  const [rankingDrawerData, setRankingDrawerData] = useState<RankingResponse | null>(null);
  const [rankingDrawerLoading, setRankingDrawerLoading] = useState(false);
  const [weightsEditorPhase, setWeightsEditorPhase] = useState<PhaseSummary | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);

  const showToast = useCallback((kind: 'success' | 'error', text: string) => {
    setToast({ kind, text, nonce: Date.now() });
    window.setTimeout(() => setToast(null), 3800);
  }, []);

  const loadRankingsForPhases = useCallback(async (phaseList: PhaseSummary[]) => {
    const next: Record<string, RankingResponse | null> = {};
    await Promise.all(
      phaseList.map(async (p) => {
        try {
          next[p.slug] = await fetchPhaseRanking(p.slug, 5);
        } catch {
          next[p.slug] = null;
        }
      }),
    );
    setRankings(next);
  }, []);

  const loadAll = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      setError(null);
      try {
        const [
          statusRes,
          configRes,
          modelsRes,
          phasesRes,
          aliasesRes,
          runsRes,
          benchmarksRes,
          channelsRes,
        ] = await Promise.all([
          fetchOpenRouterStatus().catch(() => null),
          fetchOpenRouterConfig().catch(() => null),
          fetchOpenRouterModels({ limit: 50, sort_by: 'prompt', sort_dir: 'asc' }).catch(
            () => ({ models: [], total: 0 }),
          ),
          fetchPhases().catch(() => []),
          fetchAliases().catch(() => []),
          fetchScrapeRuns(20).catch(() => []),
          fetchBenchmarks().catch(() => []),
          fetchOpenRouterDiscordChannels().catch(() => []),
        ]);

        if (statusRes) setStatus(statusRes);
        if (configRes) setConfig(configRes);
        setModels(modelsRes.models);
        setAllModels(modelsRes.models);
        setTotalModels(modelsRes.total);
        setPhases(phasesRes);
        setAliases(aliasesRes);
        setRuns(Array.isArray(runsRes) ? runsRes : runsRes?.runs ?? []);
        setBenchmarks(benchmarksRes);
        setChannels(channelsRes);

        if (phasesRes.length > 0) {
          await loadRankingsForPhases(phasesRes);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al cargar datos del plugin');
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [loadRankingsForPhases],
  );

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = window.setInterval(() => loadAll(true), 30000);
    return () => window.clearInterval(id);
  }, [autoRefresh, loadAll]);

  const handleReloadAll = async () => {
    setReloading(true);
    try {
      await loadAll(true);
      showToast('success', 'Datos refrescados');
    } catch {
      showToast('error', 'Error al refrescar');
    } finally {
      setReloading(false);
    }
  };

  const handleRefreshCatalog = async () => {
    setRefreshState('loading');
    try {
      const res = await refreshOpenRouterCatalog();
      setRefreshState('success');
      showToast('success', `${res.count ?? 0} modelos actualizados`);
      await loadAll(true);
      window.setTimeout(() => setRefreshState('idle'), 1800);
    } catch (err) {
      setRefreshState('error');
      showToast('error', err instanceof Error ? err.message : 'Error al refrescar catálogo');
      window.setTimeout(() => setRefreshState('idle'), 1800);
    }
  };

  const handleTriggerScrape = async (source: string) => {
    try {
      await triggerScrape(source);
      showToast('success', `Scrape ${source} ejecutado`);
      await loadAll(true);
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error en scrape');
      throw err;
    }
  };

  const handleTogglePhase = async (slug: string, enabled: boolean) => {
    if (!config) return;
    const next = new Set(config.phases_enabled);
    if (enabled) next.add(slug);
    else next.delete(slug);
    const arr = Array.from(next);
    try {
      const updated = await updateOpenRouterConfig({ phases_enabled: arr });
      setConfig(updated);
      showToast('success', enabled ? `Fase ${slug} activada` : `Fase ${slug} desactivada`);
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error al actualizar fases');
    }
  };

  const handleTogglePerPhaseEmbed = async () => {
    if (!config) return;
    try {
      const updated = await updateOpenRouterConfig({
        ranking_embed_per_phase: !config.ranking_embed_per_phase,
      });
      setConfig(updated);
      showToast(
        'success',
        `Embed por fase: ${updated.ranking_embed_per_phase ? 'activado' : 'desactivado'}`,
      );
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error al actualizar config');
    }
  };

  const handleShowRanking = async (slug: string) => {
    const phaseInfo = phases.find((p) => p.slug === slug) ?? null;
    if (!phaseInfo) {
      showToast('error', `Fase ${slug} no encontrada`);
      return;
    }
    setRankingDrawerPhase(phaseInfo);
    setRankingDrawerData(rankings[slug] ?? null);
    setRankingDrawerLoading(true);
    try {
      const data = await fetchPhaseRanking(slug, 10);
      setRankingDrawerData(data);
      setRankings((prev) => ({ ...prev, [slug]: data }));
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error al cargar ranking');
    } finally {
      setRankingDrawerLoading(false);
    }
  };

  const handleEditWeights = (slug: string) => {
    const phaseInfo = phases.find((p) => p.slug === slug) ?? null;
    if (!phaseInfo) {
      showToast('error', `Fase ${slug} no encontrada`);
      return;
    }
    setWeightsEditorPhase(phaseInfo);
  };

  const handleSendEmbed = async (slug: string) => {
    try {
      const res = await triggerRankingEmbed(slug);
      showToast('success', `Embed ${slug} enviado al canal ${res.channel_id}`);
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : `Error enviando embed ${slug}`);
    }
  };

  const handleWeightsSaved = async (slug: string) => {
    showToast('success', `Pesos actualizados para ${slug}`);
    // Refrescar ranking de la fase afectada
    try {
      const data = await fetchPhaseRanking(slug, 5);
      setRankings((prev) => ({ ...prev, [slug]: data }));
    } catch {
      /* silent */
    }
  };

  const handleCreateAlias = () => {
    showToast('success', 'Crear alias manual (modal pendiente)');
  };

  const handleSaveConfig = async (patch: Partial<OpenRouterConfigType>) => {
    setSaveState('saving');
    try {
      const updated = await updateOpenRouterConfig(patch);
      setConfig(updated);
      setSaveState('success');
      showToast('success', 'Configuración guardada');
      window.setTimeout(() => setSaveState('idle'), 1800);
    } catch (err) {
      setSaveState('error');
      showToast('error', err instanceof Error ? err.message : 'Error al guardar');
      window.setTimeout(() => setSaveState('idle'), 1800);
      throw err;
    }
  };

  const handleShowAll = async () => {
    setModalOpen(true);
    try {
      const res = await fetchOpenRouterModels({ limit: 500 });
      setAllModels(res.models);
      setTotalModels(res.total);
    } catch {
      // mantener allModels previos
    }
  };

  if (loading) {
    return (
      <section className="fixed top-20 bottom-0 left-64 right-0 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl text-secondary animate-openrouter-spin">
            progress_activity
          </span>
          <p className="text-on-surface-variant font-body-md">
            Cargando configuración de OpenRouter Prices...
          </p>
        </div>
      </section>
    );
  }

  if (error && !status && !config) {
    return (
      <section className="fixed top-20 bottom-0 left-64 right-0 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-error">
          <span className="material-symbols-outlined text-4xl">error</span>
          <p className="font-body-md">{error}</p>
          <button
            onClick={() => loadAll()}
            className="bg-secondary text-white px-6 py-2 rounded-lg font-label-sm"
          >
            Reintentar
          </button>
        </div>
      </section>
    );
  }

  const aaHealth = status?.scrape_health?.artificial_analysis ?? null;
  const bfclHealth = status?.scrape_health?.bfcl ?? null;
  const enabledPhases = config?.phases_enabled ?? [];

  // Total aliases-missed sumando últimos runs por source
  const aaMissed = runs
    .filter((r) => r.source === 'artificial_analysis')
    .slice(0, 1)
    .reduce((acc, r) => acc + (r.aliases_missed ?? 0), 0);
  const bfclMissed = runs
    .filter((r) => r.source === 'bfcl' || r.source === 'bfcl_github')
    .slice(0, 1)
    .reduce((acc, r) => acc + (r.aliases_missed ?? 0), 0);
  const totalAliasesMissed = aaMissed + bfclMissed;

  return (
    <section
      aria-label="OpenRouter Prices"
      className="fixed top-20 bottom-0 left-64 right-0 px-margin-desktop py-4 overflow-y-auto"
    >
      <div className="max-w-[1400px] mx-auto flex flex-col gap-4">
        <PageHeader
          onBack={() => onNavigate?.('plugins')}
          nextScrapeIn={status?.last_fetched_at ? 'en próximas horas' : null}
          autoRefresh={autoRefresh}
          onToggleAutoRefresh={() => setAutoRefresh((v) => !v)}
          onReloadAll={handleReloadAll}
          reloading={reloading}
        />

        {/* Sección 1: Status + Salud scrapers */}
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-12 lg:col-span-8 animate-openrouter-card-enter animate-openrouter-stagger-1">
            <StatusCard
              status={status}
              loading={loading}
              refreshState={refreshState}
              onRefresh={handleRefreshCatalog}
            />
          </div>
          <div className="col-span-12 lg:col-span-4 flex flex-col gap-3">
            <div className="animate-openrouter-card-enter animate-openrouter-stagger-2">
              <ScrapeHealthCard
                label="Artificial Analysis"
                source="artificial_analysis"
                health={aaHealth}
                onTrigger={handleTriggerScrape}
                aliasesMissed={aaMissed}
                onOpenAliases={() => setAliasesOpen(true)}
              />
            </div>
            <div className="animate-openrouter-card-enter animate-openrouter-stagger-3">
              <ScrapeHealthCard
                label="BFCL"
                source="bfcl"
                health={bfclHealth}
                onTrigger={handleTriggerScrape}
                aliasesMissed={bfclMissed}
                onOpenAliases={() => setAliasesOpen(true)}
              />
            </div>
          </div>
        </div>

        {/* Sección 1.5: Configuración rápida (AA API key + Discord channel + max_models + TTL) */}
        <div className="animate-openrouter-card-enter animate-openrouter-stagger-4">
          <ConfigCard
            config={config}
            channels={channels}
            saving={saveState === 'saving'}
            saveState={saveState}
            onSave={handleSaveConfig}
          />
        </div>

        {/* Sección 2: Fases SDD */}
        <div className="animate-openrouter-card-enter animate-openrouter-stagger-5">
          <PhasesGrid
            phases={phases}
            rankings={rankings}
            enabledPhases={enabledPhases}
            perPhaseEmbed={config?.ranking_embed_per_phase ?? true}
            onTogglePhase={handleTogglePhase}
            onTogglePerPhaseEmbed={handleTogglePerPhaseEmbed}
            onShowRanking={handleShowRanking}
            onEditWeights={handleEditWeights}
            onSendEmbed={handleSendEmbed}
          />
        </div>

        {/* Sección 3: Catálogo de modelos + Discord preview */}
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-12 lg:col-span-7 animate-openrouter-card-enter animate-openrouter-stagger-6">
            <ModelsTable
              models={models}
              loading={loading}
              total={totalModels}
              onShowAll={handleShowAll}
            />
          </div>
          <div className="col-span-12 lg:col-span-5 animate-openrouter-card-enter animate-openrouter-stagger-7 min-h-[28rem]">
            <DiscordPreviewCard
              models={models}
              maxCount={config?.max_models_command ?? 5}
              botName={botName}
              botAvatarUrl={botAvatarUrl}
              phases={phases}
              rankings={rankings}
            />
          </div>
        </div>

        {/* Sección 4: Historial + Benchmarks */}
        <div className="grid grid-cols-12 gap-4 pb-6">
          <div className="col-span-12 lg:col-span-6 animate-openrouter-card-enter animate-openrouter-stagger-9">
            <ScrapeHistoryCard runs={runs} loading={loading} />
          </div>
          <div className="col-span-12 lg:col-span-6 animate-openrouter-card-enter animate-openrouter-stagger-10">
            <BenchmarksCard
              benchmarks={benchmarks}
              loading={loading}
              onManage={() => showToast('success', 'Editor de pesos (modal pendiente)')}
            />
          </div>
        </div>

        {/* Modal de catálogo completo */}
        <ModelsModal
          open={modalOpen}
          models={allModels}
          total={totalModels}
          onClose={() => setModalOpen(false)}
        />

        {/* Drawer de aliases (matching de nombres) */}
        <AliasesDrawer
          open={aliasesOpen}
          aliases={aliases}
          aliasesMissed={totalAliasesMissed}
          loading={loading}
          onClose={() => setAliasesOpen(false)}
          onCreateAlias={handleCreateAlias}
        />

        {/* Drawer ranking top 10 por fase */}
        <RankingDrawer
          open={rankingDrawerPhase !== null}
          phase={rankingDrawerPhase}
          ranking={rankingDrawerData}
          loading={rankingDrawerLoading}
          onClose={() => setRankingDrawerPhase(null)}
        />

        {/* Modal editor de pesos por fase */}
        <WeightsEditor
          open={weightsEditorPhase !== null}
          phase={weightsEditorPhase}
          onClose={() => setWeightsEditorPhase(null)}
          onSaved={handleWeightsSaved}
        />

        {/* Toast feedback */}
        {toast && (
          <div
            key={toast.nonce}
            className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 animate-openrouter-toast-slide ${
              toast.kind === 'success'
                ? 'bg-secondary text-white'
                : 'bg-error text-on-error'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">
              {toast.kind === 'success' ? 'check_circle' : 'error'}
            </span>
            <span className="text-sm font-medium">{toast.text}</span>
          </div>
        )}
      </div>
    </section>
  );
}
