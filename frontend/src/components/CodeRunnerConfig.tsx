import { useCallback, useEffect, useState } from 'react';
import './code_runner/base.css';
import './code_runner/animations.css';
import PageHeader from './code_runner/PageHeader';
import GeneralStatusCard from './code_runner/GeneralStatusCard';
import MetricsCard from './code_runner/MetricsCard';
import ExecutionCard from './code_runner/ExecutionCard';
import SecurityCard from './code_runner/SecurityCard';
import SessionsTable from './code_runner/SessionsTable';
import ExecutionsList from './code_runner/ExecutionsList';
import AnimatedSaveButton from './code_runner/AnimatedSaveButton';
import {
  closeSession,
  fetchCodeRunnerChannels,
  fetchCodeRunnerConfig,
  fetchCodeRunnerExecutions,
  fetchCodeRunnerRoles,
  fetchCodeRunnerSessions,
  fetchCodeRunnerStats,
  fetchCodeRunnerStatus,
  republishLobby,
  updateCodeRunnerConfig,
  type CodeRunnerConfig as CodeRunnerConfigType,
  type CodeRunnerDiscordChannel,
  type CodeRunnerDiscordRole,
  type CodeRunnerExecution,
  type CodeRunnerSession,
  type CodeRunnerStats,
  type CodeRunnerStatus,
} from '@/api/code-runner';
import { fetchMinimaxModels, type MinimaxModel } from '@/api/ai-chat';

interface Props {
  onNavigate?: (section: string) => void;
}

interface Toast {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

type SaveState = 'idle' | 'saving' | 'success' | 'error';

const DEFAULT_CONFIG: CodeRunnerConfigType = {
  trigger_channel_id: null,
  lobby_message_id: null,
  enabled: true,
  allowed_languages: ['python', 'javascript', 'typescript', 'bash'],
  max_code_chars: 4000,
  max_output_chars: 4000,
  exec_timeout_seconds: 10,
  session_timeout_minutes: 30,
  cooldown_seconds: 10,
  max_infractions: 3,
  security_model: 'MiniMax-M2.7',
  security_enabled: true,
  mod_role_names: ['Moderador', 'Admin', 'Administrador'],
  category_id: null,
  piston_url: 'http://piston:2000/api/v2',
};

export default function CodeRunnerConfig({ onNavigate }: Props) {
  const [config, setConfig] = useState<CodeRunnerConfigType | null>(null);
  const [draft, setDraft] = useState<CodeRunnerConfigType>(DEFAULT_CONFIG);
  const [status, setStatus] = useState<CodeRunnerStatus | null>(null);
  const [stats, setStats] = useState<CodeRunnerStats | null>(null);
  const [sessions, setSessions] = useState<CodeRunnerSession[]>([]);
  const [executions, setExecutions] = useState<CodeRunnerExecution[]>([]);
  const [channels, setChannels] = useState<CodeRunnerDiscordChannel[]>([]);
  const [roles, setRoles] = useState<CodeRunnerDiscordRole[]>([]);
  const [models, setModels] = useState<MinimaxModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);
  const [republishing, setRepublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [toast, setToast] = useState<Toast | null>(null);

  const showToast = useCallback((kind: 'success' | 'error', text: string) => {
    setToast({ kind, text, nonce: Date.now() });
    window.setTimeout(() => setToast(null), 3500);
  }, []);

  const loadAll = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const [cfg, st, sess, exec, stt, ch, rl, mdl] = await Promise.all([
        fetchCodeRunnerConfig(),
        fetchCodeRunnerStatus().catch(() => null),
        fetchCodeRunnerSessions({ limit: 50 }).catch(() => []),
        fetchCodeRunnerExecutions(20).catch(() => []),
        fetchCodeRunnerStats().catch(() => null),
        fetchCodeRunnerChannels().catch(() => []),
        fetchCodeRunnerRoles().catch(() => []),
        fetchMinimaxModels().catch(() => [] as MinimaxModel[]),
      ]);
      setConfig(cfg);
      setDraft(cfg);
      setStatus(st);
      setSessions(sess);
      setExecutions(exec);
      setStats(stt);
      setChannels(ch);
      setRoles(rl);
      setModels(mdl);
      setModelsLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar configuración');
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  // Refresh en vivo SOLO de datos volátiles (sesiones, ejecuciones, stats,
  // status). NO toca config/draft para no pisar ediciones del usuario.
  const pollLive = useCallback(async () => {
    try {
      const [st, sess, exec, stt] = await Promise.all([
        fetchCodeRunnerStatus().catch(() => null),
        fetchCodeRunnerSessions({ limit: 50 }).catch(() => null),
        fetchCodeRunnerExecutions(20).catch(() => null),
        fetchCodeRunnerStats().catch(() => null),
      ]);
      if (st) setStatus(st);
      if (sess) setSessions(sess);
      if (exec) setExecutions(exec);
      if (stt) setStats(stt);
    } catch {
      /* silencioso: el siguiente tick reintenta */
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void pollLive();
    }, 6000);
    return () => window.clearInterval(id);
  }, [pollLive]);

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

  const handlePatch = (patch: Partial<CodeRunnerConfigType>) => {
    setDraft((prev) => ({ ...prev, ...patch }));
  };

  const isDirty = config ? JSON.stringify(draft) !== JSON.stringify(config) : false;

  const handleSave = async () => {
    setSaveState('saving');
    try {
      // 'enabled' se preserva tal cual en backend; este dashboard no lo edita.
      const updated = await updateCodeRunnerConfig({
        trigger_channel_id: draft.trigger_channel_id,
        category_id: draft.category_id,
        allowed_languages: draft.allowed_languages,
        max_code_chars: draft.max_code_chars,
        max_output_chars: draft.max_output_chars,
        exec_timeout_seconds: draft.exec_timeout_seconds,
        session_timeout_minutes: draft.session_timeout_minutes,
        cooldown_seconds: draft.cooldown_seconds,
        max_infractions: draft.max_infractions,
        security_model: draft.security_model,
        security_enabled: draft.security_enabled,
        mod_role_names: draft.mod_role_names,
        piston_url: draft.piston_url,
      });
      setConfig(updated);
      setDraft(updated);
      setSaveState('success');
      showToast('success', 'Configuración guardada');
      window.setTimeout(() => setSaveState('idle'), 1800);
    } catch (err) {
      setSaveState('error');
      showToast('error', err instanceof Error ? err.message : 'Error al guardar');
      window.setTimeout(() => setSaveState('idle'), 1800);
    }
  };

  const handleRepublish = async () => {
    setRepublishing(true);
    try {
      const res = await republishLobby();
      if (res.published) {
        showToast('success', `Lobby ${res.action === 'created' ? 'publicado' : 'actualizado'}`);
        await loadAll(true);
      } else {
        showToast('error', res.reason || 'No se pudo republicar');
      }
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error al republicar');
    } finally {
      setRepublishing(false);
    }
  };

  const handleCloseSession = async (sessionId: number) => {
    try {
      await closeSession(sessionId);
      showToast('success', `Sesión #${sessionId} cerrada`);
      await loadAll(true);
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Error al cerrar sesión');
    }
  };

  if (loading) {
    return (
      <section className="fixed top-20 bottom-0 left-64 right-0 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl text-secondary animate-cr-spin">progress_activity</span>
          <p className="text-on-surface-variant font-body-md">Cargando configuración de Code Runner...</p>
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
      aria-label="Code Runner"
      className="fixed top-20 bottom-0 left-64 right-0 px-margin-desktop py-4 overflow-y-auto"
    >
      <div className="max-w-[1400px] mx-auto flex flex-col gap-4">
        <PageHeader
          onBack={() => onNavigate?.('plugins')}
          enabled={draft.enabled}
          ready={status?.ready ?? false}
          expiredPending={status?.expired_pending ?? 0}
          reloading={reloading}
          onReload={handleReload}
        />

        <header className="mb-2">
          <h2 className="font-headline-lg text-headline-lg text-primary mb-1">Code Runner</h2>
          <p className="font-body-md text-on-surface-variant max-w-3xl">
            Entorno de ejecución seguro con sandbox Piston, sesiones efímeras de Discord y análisis pre-ejecución vía
            MiniMax.
          </p>
        </header>

        <div className="grid grid-cols-12 gap-4 items-stretch">
          <div className="col-span-12 lg:col-span-8 flex">
            <GeneralStatusCard
              config={draft}
              channels={channels}
              republishing={republishing}
              onPatch={handlePatch}
              onRepublish={handleRepublish}
            />
          </div>
          <div className="col-span-12 lg:col-span-4 flex">
            <MetricsCard stats={stats} />
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4 items-stretch">
          <div className="col-span-12 lg:col-span-6 flex">
            <ExecutionCard config={draft} status={status} onPatch={handlePatch} />
          </div>
          <div className="col-span-12 lg:col-span-6 flex">
            <SecurityCard
              config={draft}
              models={models}
              modelsLoading={modelsLoading}
              roles={roles}
              onPatch={handlePatch}
            />
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-12">
            <SessionsTable sessions={sessions} onClose={handleCloseSession} />
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4 pb-6">
          <div className="col-span-12">
            <ExecutionsList executions={executions} />
          </div>
        </div>

        <div className="cr-savebar">
          <div className="text-[12px] text-on-surface-variant">
            {isDirty
              ? 'Tienes cambios sin guardar.'
              : 'Configuración sincronizada con el bot.'}
          </div>
          <AnimatedSaveButton
            state={saveState}
            dirty={isDirty}
            onClick={() => void handleSave()}
            label="Guardar configuración"
          />
        </div>

        {toast && (
          <div
            key={toast.nonce}
            className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 animate-cr-toast-slide ${
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
        .cr-savebar {
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
        html.dark .cr-savebar {
          background: rgba(34, 36, 34, 0.85);
          border-color: rgba(255, 255, 255, 0.08);
          box-shadow: 0 -8px 28px rgba(0, 0, 0, 0.4);
        }
      `}</style>
    </section>
  );
}
