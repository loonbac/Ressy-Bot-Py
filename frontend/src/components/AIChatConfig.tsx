import { useCallback, useEffect, useRef, useState } from 'react';
import './ai_chat/base.css';
import './ai_chat/animations.css';
import PageHeader from './ai_chat/PageHeader';
import StatusCard from './ai_chat/StatusCard';
import BehaviorCard from './ai_chat/BehaviorCard';
import PlaygroundCard from './ai_chat/PlaygroundCard';
import MemoryToolsCard from './ai_chat/MemoryToolsCard';
import WebSearchCard from './ai_chat/WebSearchCard';
import AnimatedSaveButton from './ai_chat/AnimatedSaveButton';
import {
  fetchAIChatConfig,
  fetchAIChatStatus,
  fetchMinimaxModels,
  updateAIChatConfig,
  type AIChatConfig as AIChatConfigType,
  type AIChatStatus,
  type MinimaxModel,
} from '@/api/ai-chat';

interface Props {
  onNavigate?: (section: string) => void;
}

interface Toast {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

type SaveState = 'idle' | 'saving' | 'success' | 'error';

const DEFAULT_CONFIG: AIChatConfigType = {
  enabled: true,
  chat_model: 'MiniMax-M3',
  analysis_model: 'MiniMax-M3',
  system_prompt: '',
  max_context_messages: 60,
  rate_limit_seconds: 8,
  context_token_budget: 200000,
  summary_enabled: true,
  summary_trigger_messages: 40,
  memory_enabled: true,
  max_input_chars: 8000,
  tools_enabled: true,
  tools_search_scan_limit: 300,
  // Búsqueda web (DuckDuckGo Lite) — REQ-SEARCH-10.
  search_enabled: true,
  search_safe: true,
  search_max_per_hour: 10,
};

export default function AIChatConfig({ onNavigate }: Props) {
  const [config, setConfig] = useState<AIChatConfigType | null>(null);
  const [draft, setDraft] = useState<AIChatConfigType>(DEFAULT_CONFIG);
  const [status, setStatus] = useState<AIChatStatus | null>(null);
  const [models, setModels] = useState<MinimaxModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [configSaveState, setConfigSaveState] = useState<SaveState>('idle');
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const dirty = useRef(false);

  const showToast = useCallback((kind: 'success' | 'error', text: string) => {
    setToast({ kind, text, nonce: Date.now() });
    window.setTimeout(() => setToast(null), 3500);
  }, []);

  const loadAll = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      setError(null);
      try {
        const [cfg, st, mdl] = await Promise.all([
          fetchAIChatConfig(),
          fetchAIChatStatus().catch(() => null),
          fetchMinimaxModels().catch(() => [] as MinimaxModel[]),
        ]);
        setConfig(cfg);
        setDraft(cfg);
        setStatus(st);
        setModels(mdl);
        setModelsLoading(false);
        dirty.current = false;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al cargar configuración');
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const handleReload = async () => {
    setReloading(true);
    try {
      await loadAll(true);
      showToast('success', 'Datos recargados');
    } catch {
      showToast('error', 'Error al recargar');
    } finally {
      setReloading(false);
    }
  };

  const handlePatchDraft = (patch: Partial<AIChatConfigType>) => {
    setDraft((prev) => {
      const next = { ...prev, ...patch };
      dirty.current = JSON.stringify(next) !== JSON.stringify(config);
      return next;
    });
  };

  const isDirty = config ? JSON.stringify(draft) !== JSON.stringify(config) : false;

  const handleSaveConfig = async () => {
    setConfigSaveState('saving');
    try {
      // enabled y analysis_model se preservan tal cual en backend; este
      // dashboard edita modelo, prompt, contexto, memoria y tools.
      const updated = await updateAIChatConfig({
        chat_model: draft.chat_model,
        system_prompt: draft.system_prompt,
        max_context_messages: draft.max_context_messages,
        rate_limit_seconds: draft.rate_limit_seconds,
        context_token_budget: draft.context_token_budget,
        summary_enabled: draft.summary_enabled,
        memory_enabled: draft.memory_enabled,
        tools_enabled: draft.tools_enabled,
        tools_search_scan_limit: draft.tools_search_scan_limit,
        // Búsqueda web (DuckDuckGo Lite) — REQ-SEARCH-10.
        search_enabled: draft.search_enabled,
        search_safe: draft.search_safe,
        search_max_per_hour: draft.search_max_per_hour,
      });
      setConfig(updated);
      setDraft(updated);
      setConfigSaveState('success');
      showToast('success', 'Configuración guardada');
      window.setTimeout(() => setConfigSaveState('idle'), 1800);
    } catch (err) {
      setConfigSaveState('error');
      showToast('error', err instanceof Error ? err.message : 'Error al guardar');
      window.setTimeout(() => setConfigSaveState('idle'), 1800);
    }
  };

  if (loading) {
    return (
      <section className="fixed top-20 bottom-0 left-64 right-0 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl text-secondary animate-ai-chat-spin">
            progress_activity
          </span>
          <p className="text-on-surface-variant font-body-md">Cargando configuración de Chat IA...</p>
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
            type="button"
            onClick={() => loadAll()}
            className="bg-secondary text-white px-6 py-2 rounded-lg font-label-sm"
          >
            Reintentar
          </button>
        </div>
      </section>
    );
  }

  return (
    <section
      aria-label="AI Chat MiniMax"
      className="fixed top-20 bottom-0 left-64 right-0 px-margin-desktop py-4 overflow-y-auto"
    >
      <div className="max-w-[1400px] mx-auto flex flex-col gap-4">
        <PageHeader
          onBack={() => onNavigate?.('plugins')}
          ready={status?.ready ?? false}
          enabled={draft.enabled}
          reloading={reloading}
          onReload={handleReload}
        />

        <header className="mb-2">
          <h2 className="font-headline-lg text-headline-lg text-primary mb-1">Configuración de Chat IA</h2>
          <p className="font-body-md text-on-surface-variant max-w-3xl">
            Sincroniza la sabiduría artificial de MiniMax con la serenidad de tu comunidad. Ajusta modelos, tono
            y límites de respuesta sin reiniciar el bot.
          </p>
        </header>

        <div className="grid grid-cols-12 gap-4 items-stretch">
          <div className="col-span-12 lg:col-span-4 flex">
            <StatusCard
              config={draft}
              models={models}
              modelsLoading={modelsLoading}
              onPatch={handlePatchDraft}
            />
          </div>
          <div className="col-span-12 lg:col-span-8 flex">
            <BehaviorCard config={draft} onPatch={handlePatchDraft} />
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4 items-stretch">
          <div className="col-span-12 lg:col-span-7 flex">
            <PlaygroundCard config={draft} showToast={showToast} />
          </div>
          <div className="col-span-12 lg:col-span-5 flex">
            <WebSearchCard config={draft} onPatch={handlePatchDraft} />
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4 pb-6">
          <div className="col-span-12 lg:col-span-12 flex">
            <MemoryToolsCard showToast={showToast} />
          </div>
        </div>

        <div className="ai-chat-savebar">
          <div className="text-[12px] text-on-surface-variant">
            {isDirty
              ? 'Tienes cambios sin guardar en la configuración del plugin.'
              : 'Configuración sincronizada con el bot.'}
          </div>
          <AnimatedSaveButton
            state={configSaveState}
            dirty={isDirty}
            onClick={() => void handleSaveConfig()}
            label="Guardar configuración"
          />
        </div>

        {toast && (
          <div
            key={toast.nonce}
            className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 animate-ai-chat-toast-slide ${
              toast.kind === 'success' ? 'bg-secondary text-white' : 'bg-error text-on-error'
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">
              {toast.kind === 'success' ? 'check_circle' : 'error'}
            </span>
            <span className="text-sm font-medium">{toast.text}</span>
          </div>
        )}
      </div>

      <style>{`
        .ai-chat-savebar {
          position: sticky;
          bottom: 0;
          z-index: 20;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          padding: 0.85rem 1.2rem;
          background: rgba(250, 249, 246, 0.9);
          backdrop-filter: blur(14px);
          border: 1px solid rgba(210, 195, 197, 0.32);
          border-radius: 1rem;
          box-shadow: 0 -8px 28px rgba(168, 0, 33, 0.08);
        }
        html.dark .ai-chat-savebar {
          background: rgba(34, 36, 34, 0.85);
          border-color: rgba(255, 255, 255, 0.08);
          box-shadow: 0 -8px 28px rgba(0, 0, 0, 0.4);
        }
      `}</style>
    </section>
  );
}
