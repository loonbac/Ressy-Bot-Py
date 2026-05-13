import { useState, useEffect, useCallback } from 'react';
import {
  YouTubeSubscription,
  type YouTubeConfig as YouTubeConfigType,
  DiscordChannel,
  type YouTubeSearchResult,
  fetchYouTubeSubscriptions,
  addYouTubeSubscription,
  removeYouTubeSubscription,
  toggleYouTubeNotifications,
  fetchYouTubeConfig,
  updateYouTubeConfig,
  fetchDiscordChannels,
  testNotifyLatest,
} from '@/api/youtube';
import { type SaveState } from './youtube/AnimatedSaveButton';
import { type TestState } from './youtube/AnimatedTestButton';
import ChannelAddedToast from './youtube/ChannelAddedToast';
import PageHeader from './youtube/PageHeader';
import ChannelsListCard from './youtube/ChannelsListCard';
import MessageSettingsCard from './youtube/MessageSettingsCard';
import FiltersCard from './youtube/FiltersCard';
import ConnectionCard from './youtube/ConnectionCard';
import FooterActions, { type TestFeedback } from './youtube/FooterActions';

export default function YouTubeConfig() {
  const [subscriptions, setSubscriptions] = useState<YouTubeSubscription[]>([]);
  const [config, setConfig] = useState<YouTubeConfigType | null>(null);
  const [discordChannels, setDiscordChannels] = useState<DiscordChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [newChannelId, setNewChannelId] = useState<string | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [toastChannel, setToastChannel] = useState<string | null>(null);
  const [testState, setTestState] = useState<TestState>('idle');
  const [testCount, setTestCount] = useState<number>(1);
  const [testFeedback, setTestFeedback] = useState<TestFeedback | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [subs, cfg, channels] = await Promise.all([
        fetchYouTubeSubscriptions(),
        fetchYouTubeConfig(),
        fetchDiscordChannels(),
      ]);
      setSubscriptions(subs);
      setConfig(cfg);
      setDiscordChannels(channels);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar datos');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAddChannel = async (result: YouTubeSearchResult) => {
    await addYouTubeSubscription(result.channel_id, result.channel_name, result.thumbnail);
    const subs = await fetchYouTubeSubscriptions();
    setSubscriptions(subs);
    setNewChannelId(result.channel_id);
    setToastChannel(result.channel_name);
    setTimeout(() => setNewChannelId(null), 1500);
  };

  const handleDeleteChannel = async (channelId: string) => {
    setDeletingIds((prev) => new Set(prev).add(channelId));
    try {
      await removeYouTubeSubscription(channelId);
      setTimeout(() => {
        setSubscriptions((prev) => prev.filter((s) => s.channel_id !== channelId));
        setDeletingIds((prev) => {
          const n = new Set(prev);
          n.delete(channelId);
          return n;
        });
      }, 320);
    } catch (err) {
      setDeletingIds((prev) => {
        const n = new Set(prev);
        n.delete(channelId);
        return n;
      });
      setError(err instanceof Error ? err.message : 'Error al eliminar canal');
    }
  };

  const handleToggleNotifications = async (channelId: string, enabled: boolean) => {
    try {
      await toggleYouTubeNotifications(channelId, enabled);
      setSubscriptions((prev) =>
        prev.map((s) => (s.channel_id === channelId ? { ...s, notifications_enabled: enabled } : s))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cambiar notificaciones');
    }
  };

  const handleSave = async () => {
    if (!config) return;
    setSaveState('saving');
    try {
      const updated = await updateYouTubeConfig(config);
      setConfig(updated);
      setSaveState('success');
      setTimeout(() => setSaveState('idle'), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar');
      setSaveState('error');
      setTimeout(() => setSaveState('idle'), 2000);
    }
  };

  const updateField = <K extends keyof YouTubeConfigType>(key: K, value: YouTubeConfigType[K]) => {
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const handleChannelChange = async (newId: string | null) => {
    if (!config) return;
    const next: YouTubeConfigType = { ...config, discord_channel_id: newId };
    setConfig(next);
    try {
      const updated = await updateYouTubeConfig(next);
      setConfig(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar canal');
    }
  };

  const showFeedback = (kind: 'success' | 'error', text: string) => {
    setTestFeedback({ kind, text, nonce: Date.now() });
    window.setTimeout(() => {
      setTestFeedback((prev) => (prev && prev.text === text ? null : prev));
    }, 4200);
  };

  const handleTestNotify = async () => {
    setTestState('testing');
    setTestFeedback(null);
    try {
      const result = await testNotifyLatest(testCount);
      if (!result.has_api_key) {
        setTestState('error');
        showFeedback('error', 'No hay Google API Key configurada');
        window.setTimeout(() => setTestState('idle'), 1600);
        return;
      }
      if (result.channels_checked === 0) {
        setTestState('error');
        showFeedback('error', 'No hay canales sincronizados');
        window.setTimeout(() => setTestState('idle'), 1600);
        return;
      }

      const errors = result.diagnostics.filter((d) => d.status === 'error');
      if (errors.length > 0 && result.total_sent === 0) {
        const firstError = errors[0];
        setTestState('error');
        showFeedback(
          'error',
          `${firstError.channel_name || firstError.channel_id}: ${firstError.error ?? 'error'}`
        );
        window.setTimeout(() => setTestState('idle'), 1600);
        return;
      }

      setTestState('success');
      showFeedback(
        'success',
        `${result.total_sent} mensaje(s) enviado(s) a Discord${
          errors.length > 0 ? ` (${errors.length} canal(es) con error)` : ''
        }`
      );
      window.setTimeout(() => setTestState('idle'), 1600);
    } catch (err) {
      setTestState('error');
      showFeedback('error', err instanceof Error ? err.message : 'Error desconocido');
      window.setTimeout(() => setTestState('idle'), 1600);
    }
  };

  if (loading) {
    return (
      <section className="min-h-[calc(100vh-7rem)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl text-secondary animate-spin">
            progress_activity
          </span>
          <p className="text-on-surface-variant font-body-md">Cargando configuración de YouTube...</p>
        </div>
      </section>
    );
  }

  if (error && !config) {
    return (
      <section className="min-h-[calc(100vh-7rem)] flex items-center justify-center">
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

  return (
    <section className="-mx-margin-desktop px-margin-desktop pt-6 pb-10">
      <div className="max-w-container-max mx-auto relative z-10 flex flex-col gap-5">
        <PageHeader />

        {error && (
          <div className="p-3 bg-error-container/50 border border-error/20 rounded-lg flex items-center gap-3 text-error">
            <span className="material-symbols-outlined text-[18px]">error</span>
            <span className="font-body-md text-sm">{error}</span>
          </div>
        )}

        <div className="grid grid-cols-12 gap-5 items-start">
          <div className="col-span-12 lg:col-span-7">
            <ChannelsListCard
              subscriptions={subscriptions}
              newChannelId={newChannelId}
              deletingIds={deletingIds}
              onToggleNotifications={handleToggleNotifications}
              onDeleteChannel={handleDeleteChannel}
              onAddChannel={handleAddChannel}
            />
          </div>

          <aside className="col-span-12 lg:col-span-5 flex flex-col gap-5">
            {config && (
              <>
                <MessageSettingsCard
                  config={config}
                  discordChannels={discordChannels}
                  onMessageChange={(v) => updateField('announcement_message', v)}
                  onChannelChange={handleChannelChange}
                />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <FiltersCard
                    config={config}
                    onFilterShortsChange={(v) => updateField('filter_shorts', v)}
                    onFilterPremieresChange={(v) => updateField('filter_premieres', v)}
                    onFilterMinDurationChange={(v) => updateField('filter_min_duration', v)}
                  />
                  <ConnectionCard
                    config={config}
                    onCallbackUrlChange={(v) => updateField('callback_url', v)}
                    onApiKeyChange={(v) => updateField('google_api_key', v)}
                  />
                </div>
              </>
            )}
          </aside>
        </div>

        <FooterActions
          saveState={saveState}
          testState={testState}
          testCount={testCount}
          testFeedback={testFeedback}
          onSave={handleSave}
          onTest={handleTestNotify}
          onTestCountChange={setTestCount}
        />
      </div>

      <ChannelAddedToast
        channelName={toastChannel}
        onDismiss={() => setToastChannel(null)}
      />
    </section>
  );
}
