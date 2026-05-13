import { useCallback, useEffect, useState } from 'react';
import {
  fetchBlackboardConfig,
  fetchBlackboardChannels,
  fetchBlackboardRoles,
  fetchBlackboardAssignments,
  triggerBlackboardScrape,
  sendPendingDigest,
  updateBlackboardConfig,
  type BlackboardAssignment,
  type BlackboardConfig as BlackboardConfigType,
  type BlackboardDiscordChannel,
  type BlackboardDiscordRole,
} from '@/api/blackboard';
import PageHeader from './blackboard/PageHeader';
import CredentialsCard from './blackboard/CredentialsCard';
import ScheduleCard from './blackboard/ScheduleCard';
import AssignmentsCard from './blackboard/AssignmentsCard';
import EmbedPreviewCard from './blackboard/EmbedPreviewCard';
import ConfettiBurst from './blackboard/ConfettiBurst';
import FooterActions, {
  type SaveState,
  type ScrapeState,
  type SendState,
} from './blackboard/FooterActions';
import './blackboard/animations.css';

interface Feedback {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

interface Props {
  onNavigate?: (section: string) => void;
  botName?: string;
  botAvatarUrl?: string;
}

export default function BlackboardConfig({ onNavigate, botName, botAvatarUrl }: Props) {
  const [config, setConfig] = useState<BlackboardConfigType | null>(null);
  const [channels, setChannels] = useState<BlackboardDiscordChannel[]>([]);
  const [roles, setRoles] = useState<BlackboardDiscordRole[]>([]);
  const [assignments, setAssignments] = useState<BlackboardAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [assignmentsLoading, setAssignmentsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [scrapeState, setScrapeState] = useState<ScrapeState>('idle');
  const [sendState, setSendState] = useState<SendState>('idle');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [confettiTrigger, setConfettiTrigger] = useState(0);

  const loadAssignments = useCallback(async () => {
    setAssignmentsLoading(true);
    try {
      const list = await fetchBlackboardAssignments();
      setAssignments(list);
    } catch (err) {
      console.error(err);
    } finally {
      setAssignmentsLoading(false);
    }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, chs, rls] = await Promise.all([
        fetchBlackboardConfig(),
        fetchBlackboardChannels(),
        fetchBlackboardRoles(),
      ]);
      setConfig(cfg);
      setChannels(chs);
      setRoles(rls);
      await loadAssignments();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar');
    } finally {
      setLoading(false);
    }
  }, [loadAssignments]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const updateField = <K extends keyof BlackboardConfigType>(
    key: K,
    value: BlackboardConfigType[K],
  ) => {
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const showFeedback = (kind: 'success' | 'error', text: string) => {
    setFeedback({ kind, text, nonce: Date.now() });
    window.setTimeout(() => {
      setFeedback((prev) => (prev && prev.text === text ? null : prev));
    }, 4200);
  };

  const handleSave = async () => {
    if (!config) return;
    setSaveState('saving');
    try {
      const updated = await updateBlackboardConfig(config);
      setConfig(updated);
      setSaveState('success');
      setConfettiTrigger((n) => n + 1);
      showFeedback('success', 'Configuración guardada');
      window.setTimeout(() => setSaveState('idle'), 1800);
    } catch (err) {
      setSaveState('error');
      showFeedback('error', err instanceof Error ? err.message : 'Error al guardar');
      window.setTimeout(() => setSaveState('idle'), 1800);
    }
  };

  const handleScrape = async () => {
    if (!config) return;
    setScrapeState('scraping');
    try {
      const updated = await updateBlackboardConfig(config);
      setConfig(updated);
      const result = await triggerBlackboardScrape();
      await loadAssignments();
      setScrapeState('success');
      setConfettiTrigger((n) => n + 1);
      showFeedback(
        'success',
        `${result.assignments_found} tareas encontradas (${result.new_assignments} nuevas)`,
      );
      window.setTimeout(() => setScrapeState('idle'), 1800);
    } catch (err) {
      setScrapeState('error');
      showFeedback('error', err instanceof Error ? err.message : 'Error al scrapear');
      window.setTimeout(() => setScrapeState('idle'), 1800);
    }
  };

  const handleSendPending = async () => {
    if (!config) return;
    setSendState('sending');
    try {
      const updated = await updateBlackboardConfig(config);
      setConfig(updated);
      const result = await sendPendingDigest();
      setSendState('success');
      setConfettiTrigger((n) => n + 1);
      showFeedback(
        'success',
        `Digest enviado a #${result.channel_name} (${result.pending_count} pendiente${
          result.pending_count === 1 ? '' : 's'
        })`,
      );
      window.setTimeout(() => setSendState('idle'), 1800);
    } catch (err) {
      setSendState('error');
      showFeedback('error', err instanceof Error ? err.message : 'Error al enviar pendientes');
      window.setTimeout(() => setSendState('idle'), 1800);
    }
  };

  if (loading) {
    return (
      <section className="fixed top-20 bottom-0 left-64 right-0 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl text-secondary animate-spin">
            progress_activity
          </span>
          <p className="text-on-surface-variant font-body-md">
            Cargando configuración de Blackboard...
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
            onClick={loadData}
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
      aria-label="Configuración de Blackboard"
      className="fixed top-20 bottom-0 left-64 right-0 px-margin-desktop py-4 overflow-hidden"
    >
      <div className="max-w-container-max mx-auto h-full grid grid-rows-[auto_minmax(0,1fr)_auto] gap-3 overflow-hidden">
        <PageHeader onBack={() => onNavigate?.('plugins')} />

        {error && (
          <div className="p-2.5 bg-error-container/50 border border-error/20 rounded-lg flex items-center gap-3 text-error">
            <span className="material-symbols-outlined text-[18px]">error</span>
            <span className="font-body-md text-sm">{error}</span>
          </div>
        )}

        <div
          className="grid grid-cols-12 gap-3 min-h-0 overflow-hidden"
          style={{ gridTemplateRows: 'minmax(0, 1fr) minmax(0, 1fr)' }}
        >
          {/* Row 1 */}
          <div className="col-span-12 lg:col-span-5 min-h-0 overflow-hidden animate-bb-card-enter animate-bb-card-stagger-1">
            <CredentialsCard config={config} onChange={updateField} />
          </div>
          <div className="col-span-12 lg:col-span-7 min-h-0 overflow-hidden animate-bb-card-enter animate-bb-card-stagger-2">
            <EmbedPreviewCard
              config={config}
              assignments={assignments}
              roles={roles}
              botName={botName}
              botAvatarUrl={botAvatarUrl}
            />
          </div>

          {/* Row 2 */}
          <div className="col-span-12 lg:col-span-5 min-h-0 overflow-hidden animate-bb-card-enter animate-bb-card-stagger-3">
            <ScheduleCard
              config={config}
              channels={channels}
              roles={roles}
              onChange={updateField}
            />
          </div>
          <div className="col-span-12 lg:col-span-7 min-h-0 overflow-hidden animate-bb-card-enter animate-bb-card-stagger-4">
            <AssignmentsCard
              assignments={assignments}
              loading={assignmentsLoading}
              onRefresh={loadAssignments}
            />
          </div>
        </div>

        <div className="relative">
          <FooterActions
            saveState={saveState}
            scrapeState={scrapeState}
            sendState={sendState}
            feedback={feedback}
            onSave={handleSave}
            onScrape={handleScrape}
            onSendPending={handleSendPending}
          />
          <ConfettiBurst trigger={confettiTrigger} />
        </div>
      </div>
    </section>
  );
}
