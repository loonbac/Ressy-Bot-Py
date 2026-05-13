import { useState, useEffect, useCallback, useRef } from 'react';
import {
  YouTubeSubscription,
  type YouTubeConfig as YouTubeConfigType,
  DiscordChannel,
  fetchYouTubeSubscriptions,
  addYouTubeSubscription,
  removeYouTubeSubscription,
  toggleYouTubeNotifications,
  fetchYouTubeConfig,
  updateYouTubeConfig,
  fetchDiscordChannels,
  searchYouTubeChannels,
  type YouTubeSearchResult,
  getProxiedThumbnailUrl,
  testNotifyLatest,
} from '@/api/youtube';
import ToggleSwitch from './youtube/ToggleSwitch';
import AnimatedChannelCard from './youtube/AnimatedChannelCard';
import AnimatedSaveButton, { type SaveState } from './youtube/AnimatedSaveButton';
import AnimatedTestButton, { type TestState } from './youtube/AnimatedTestButton';
import ChannelAddedToast from './youtube/ChannelAddedToast';

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
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<YouTubeSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [testState, setTestState] = useState<TestState>('idle');
  const [testCount, setTestCount] = useState<number>(1);
  const [testFeedback, setTestFeedback] = useState<{
    kind: 'success' | 'error';
    text: string;
    nonce: number;
  } | null>(null);
  const [EmbedVisualizer, setEmbedVisualizer] = useState<any>(null);
  const [embedCssLoaded, setEmbedCssLoaded] = useState(false);

  useEffect(() => {
    async function loadEmbedVisualizer() {
      try {
        const mod = await import('embed-visualizer');
        setEmbedVisualizer(() => mod.EmbedVisualizer);
        await import('embed-visualizer/dist/index.css');
        setEmbedCssLoaded(true);
      } catch (e) {
        console.error('Failed to load embed visualizer:', e);
      }
    }
    loadEmbedVisualizer();
  }, []);

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

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);
    setSearchError(null);

    if (searchTimeout.current) clearTimeout(searchTimeout.current);

    if (!value.trim()) {
      setSearchResults([]);
      return;
    }

    setSearching(true);
    searchTimeout.current = setTimeout(async () => {
      try {
        const results = await searchYouTubeChannels(value.trim());
        setSearchResults(results);
      } catch (err) {
        setSearchError(err instanceof Error ? err.message : 'Error al buscar');
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 400); // debounce 400ms
  };

  const handleSelectChannel = async (result: YouTubeSearchResult) => {
    setSearching(true);
    try {
      await addYouTubeSubscription(result.channel_id, result.channel_name, result.thumbnail);
      setSearchQuery('');
      setSearchResults([]);
      const subs = await fetchYouTubeSubscriptions();
      setSubscriptions(subs);
      setNewChannelId(result.channel_id);
      setToastChannel(result.channel_name);
      setTimeout(() => setNewChannelId(null), 1500);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Error al agregar canal');
    } finally {
      setSearching(false);
    }
  };

  const handleDeleteChannel = async (channelId: string) => {
    setDeletingIds((prev) => new Set(prev).add(channelId));
    try {
      await removeYouTubeSubscription(channelId);
      setTimeout(() => {
        setSubscriptions((prev) => prev.filter((s) => s.channel_id !== channelId));
        setDeletingIds((prev) => { const n = new Set(prev); n.delete(channelId); return n; });
      }, 320);
    } catch (err) {
      setDeletingIds((prev) => { const n = new Set(prev); n.delete(channelId); return n; });
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

  const updateConfigField = <K extends keyof YouTubeConfigType>(key: K, value: YouTubeConfigType[K]) => {
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
      <section className="h-[calc(100vh-7rem)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl text-secondary animate-spin">progress_activity</span>
          <p className="text-on-surface-variant font-body-md">Cargando configuración de YouTube...</p>
        </div>
      </section>
    );
  }

  if (error && !config) {
    return (
      <section className="h-[calc(100vh-7rem)] flex items-center justify-center">
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
    <section className="h-[calc(100vh-7rem)] -mx-margin-desktop -mt-8 px-margin-desktop pt-6 overflow-hidden flex flex-col">
      <div className="max-w-container-max mx-auto relative z-10 flex flex-col flex-1 min-h-0">
        {/* Breadcrumb & Title — compact */}
        <div className="mb-5 flex-shrink-0">
          <div className="flex items-center gap-2 text-on-surface-variant text-label-sm mb-2">
            <span className="hover:text-secondary cursor-pointer transition-colors">Plugins</span>
            <span className="material-symbols-outlined text-[14px]">chevron_right</span>
            <span className="text-secondary font-semibold">YouTube</span>
          </div>
          <h2 className="font-display text-headline-lg text-on-surface mb-1">Configuración de YouTube</h2>
          <p className="text-body-md text-on-surface-variant max-w-2xl">
            Sincroniza y gestiona las alertas de tus canales favoritos con la armonía del santuario.
          </p>
        </div>

        {error && (
          <div className="mb-3 p-3 bg-error-container/50 border border-error/20 rounded-lg flex items-center gap-3 text-error flex-shrink-0">
            <span className="material-symbols-outlined text-[18px]">error</span>
            <span className="font-body-md text-sm">{error}</span>
          </div>
        )}

        {/* Bento Grid — fills remaining space */}
        <div className="grid grid-cols-12 gap-5 flex-1 min-h-0">
          {/* Channels List Section */}
          <section className="col-span-12 lg:col-span-7 bg-surface-container-lowest/60 backdrop-blur-md rounded-xl border border-white/40 shadow-sm flex flex-col min-h-0">
            <div className="flex items-center justify-between px-6 pt-5 pb-4 flex-shrink-0 border-b border-outline-variant/10">
              <h3 className="font-headline-md text-headline-md flex items-center gap-2">
                <span className="material-symbols-outlined text-secondary text-[22px]">subscriptions</span>
                Canales Sincronizados
              </h3>
              <span className="bg-primary-fixed/30 text-on-primary-fixed-variant px-3 py-0.5 rounded-full text-label-sm">
                {subscriptions.length}
              </span>
            </div>

            {/* Scrollable channel list */}
            <div className="flex-1 min-h-0 overflow-y-auto px-6 py-3">
              {subscriptions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <span className="material-symbols-outlined text-4xl text-outline-variant mb-3">subscriptions</span>
                  <p className="text-on-surface-variant font-body-md text-sm">No hay canales sincronizados</p>
                  <p className="text-tertiary text-xs mt-1">Añade un canal para comenzar a recibir notificaciones</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {subscriptions.map((sub, index) => (
                    <AnimatedChannelCard
                      key={sub.channel_id}
                      channelId={sub.channel_id}
                      channelName={sub.channel_name}
                      thumbnailUrl={sub.thumbnail_url}
                      notificationsEnabled={sub.notifications_enabled}
                      isNew={sub.channel_id === newChannelId}
                      isDeleting={deletingIds.has(sub.channel_id)}
                      animationDelay={index * 55}
                      onToggle={(enabled) => handleToggleNotifications(sub.channel_id, enabled)}
                      onDelete={() => handleDeleteChannel(sub.channel_id)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Add Channel Search — pinned at bottom */}
            <div className="px-6 py-4 border-t border-outline-variant/15 flex-shrink-0">
              <div className="relative">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-[18px] text-secondary">add_link</span>
                  <span className="text-label-sm text-on-surface-variant font-bold uppercase">Añadir Canal</span>
                </div>
                <input
                  className="w-full bg-transparent border-b-2 border-outline-variant/30 focus:border-secondary outline-none py-2 px-1 transition-all duration-300 text-sm font-body-md placeholder:text-outline-variant"
                  placeholder="Buscar canal de YouTube..."
                  type="text"
                  value={searchQuery}
                  onChange={handleSearchChange}
                  onKeyDown={(e) => { if (e.key === 'Escape') setSearchResults([]); }}
                />

                {/* Search results dropdown */}
                {searchResults.length > 0 && (
                  <div className="absolute z-50 mt-1 w-full bg-surface-container-lowest border border-outline-variant/20 rounded-xl shadow-xl overflow-hidden max-h-48 overflow-y-auto">
                    {searchResults.map((result) => (
                      <button
                        key={result.channel_id}
                        onClick={() => handleSelectChannel(result)}
                        className="w-full flex items-center gap-3 p-3 hover:bg-primary-container/20 transition-colors text-left border-b border-outline-variant/10 last:border-b-0"
                      >
                        <img
                          src={getProxiedThumbnailUrl(result.thumbnail)}
                          alt={result.channel_name}
                          className="w-8 h-8 rounded-full border border-outline-variant/20 flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-on-surface text-sm truncate">{result.channel_name}</p>
                          <p className="text-label-sm text-tertiary truncate">{result.description}</p>
                        </div>
                        <span className="material-symbols-outlined text-secondary text-[20px]">add_circle</span>
                      </button>
                    ))}
                  </div>
                )}

                {searching && searchResults.length === 0 && searchQuery.trim() && (
                  <div className="absolute z-50 mt-1 w-full bg-surface-container-lowest border border-outline-variant/20 rounded-xl shadow-xl p-3 text-center text-tertiary text-sm">
                    <span className="material-symbols-outlined animate-spin inline-block text-[18px]">progress_activity</span>
                    <span className="ml-2">Buscando...</span>
                  </div>
                )}

                {searchError && (
                  <p className="text-error text-xs mt-1">{searchError}</p>
                )}
              </div>
            </div>
          </section>

          {/* Settings Sidebar */}
          <aside className="col-span-12 lg:col-span-5 flex flex-col gap-6 min-h-0 overflow-y-auto pr-1">
            {/* Message Settings Card — natural height; aside scrolls if needed */}
            <div className="bg-primary-fixed/20 backdrop-blur-md rounded-xl p-5 border border-primary-container/30 flex flex-col flex-shrink-0">
              <h3 className="font-headline-md text-headline-md mb-4 flex items-center gap-2 flex-shrink-0">
                <span className="material-symbols-outlined text-secondary text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                  forum
                </span>
                Ajustes de Mensaje
              </h3>
              <div className="flex flex-col gap-4">
                <div className="flex flex-col">
                  <label className="block text-label-sm text-primary font-bold uppercase mb-1.5 flex-shrink-0">
                    Mensaje de anuncio
                  </label>
                  <textarea
                    className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg p-3 text-sm font-body-md min-h-[80px] focus:ring-2 focus:ring-secondary/20 outline-none resize-none transition-all text-on-surface"
                    placeholder="@everyone ¡Hay un nuevo video en {canal}!"
                    value={config?.announcement_message ?? ''}
                    onChange={(e) => updateConfigField('announcement_message', e.target.value)}
                  />
                  <div className="mt-4">
                    <label className="block text-label-sm text-primary font-bold uppercase mb-2">
                      Vista Previa
                    </label>
                    <div className="bg-discord rounded-xl overflow-hidden" style={{ maxWidth: 520 }}>
                      {EmbedVisualizer && embedCssLoaded && config?.announcement_message !== undefined ? (
                        <EmbedVisualizer
                          embed={{
                            content:
                              (config?.announcement_message?.replace('{canal}', 'Canal de Ejemplo') || '') || undefined,
                            embed: {
                              color: 0xFF0000,
                              author: {
                                name: 'Canal de Ejemplo',
                                url: 'https://youtube.com',
                              },
                              title: 'Título del Nuevo Video',
                              url: 'https://youtube.com/watch?v=dQw4w9WgXcQ',
                              description: 'Nuevo video publicado en YouTube',
                              image: {
                                url: 'https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg',
                              },
                              footer: { text: 'YouTube' },
                              timestamp: new Date().toISOString(),
                            },
                          }}
                          onError={(e: unknown) => console.error(e)}
                        />
                      ) : (
                        <div className="bg-surface-container-low rounded-xl p-4 text-tertiary text-sm text-center">
                          Cargando vista previa...
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <label className="block text-label-sm text-primary font-bold uppercase mb-1.5">
                    Canal de Discord
                  </label>
                  <div className="relative">
                    <select
                      className="w-full appearance-none bg-surface-container-low border border-outline-variant/30 rounded-lg p-3 text-sm font-body-md focus:ring-2 focus:ring-secondary/20 outline-none cursor-pointer text-on-surface"
                      value={config?.discord_channel_id ?? ''}
                      onChange={(e) => handleChannelChange(e.target.value ? e.target.value : null)}
                    >
                      <option value="">Seleccionar canal...</option>
                      {discordChannels.map((ch) => (
                        <option key={ch.id} value={ch.id}>
                          {ch.name} — {ch.guild_name}
                        </option>
                      ))}
                    </select>
                    <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-[18px]">
                      expand_more
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Filtros + Conexión — side-by-side to save vertical space */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 flex-shrink-0">
              {/* Content Filters Card */}
              <div className="bg-surface-container-lowest/60 backdrop-blur-md rounded-xl p-4 border border-white/40 shadow-sm">
                <h3 className="font-headline-md text-headline-md mb-3 flex items-center gap-2">
                  <span className="material-symbols-outlined text-secondary text-[20px]">filter_list</span>
                  Filtros de Contenido
                </h3>
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-on-surface-variant">Omitir Shorts</span>
                    <ToggleSwitch
                      checked={config?.filter_shorts ?? false}
                      onChange={(v) => updateConfigField('filter_shorts', v)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-on-surface-variant">Omitir Estrenos</span>
                    <ToggleSwitch
                      checked={config?.filter_premieres ?? false}
                      onChange={(v) => updateConfigField('filter_premieres', v)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-on-surface-variant">Solo videos &gt; 5 min</span>
                    <ToggleSwitch
                      checked={(config?.filter_min_duration ?? 0) > 0}
                      onChange={(v) => updateConfigField('filter_min_duration', v ? 300 : 0)}
                    />
                  </div>
                </div>
              </div>

              {/* Connection Settings Card */}
              <div className="bg-surface-container-lowest/60 backdrop-blur-md rounded-xl p-4 border border-white/40 shadow-sm">
                <h3 className="font-headline-md text-headline-md mb-3 flex items-center gap-2">
                  <span className="material-symbols-outlined text-secondary text-[20px]">link</span>
                  Conexión
                </h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-label-sm text-primary font-bold uppercase mb-1">
                      URL de Callback
                    </label>
                    <input
                      type="url"
                      className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg py-2 px-3 text-sm font-body-md focus:ring-2 focus:ring-secondary/20 outline-none transition-all text-on-surface"
                      placeholder="https://tu-dominio.ngrok-free.app"
                      value={config?.callback_url ?? ''}
                      onChange={(e) => updateConfigField('callback_url', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-label-sm text-primary font-bold uppercase mb-1">
                      Google API Key
                    </label>
                    <input
                      type="password"
                      className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg py-2 px-3 text-sm font-body-md focus:ring-2 focus:ring-secondary/20 outline-none transition-all text-on-surface"
                      placeholder="AIzaSy..."
                      value={config?.google_api_key ?? ''}
                      onChange={(e) => updateConfigField('google_api_key', e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </div>
          </aside>

          {/* Footer Actions */}
          <div className="col-span-12 flex flex-wrap justify-end items-center gap-3 py-3 px-5 bg-surface-container-low/40 rounded-xl border border-outline-variant/10 flex-shrink-0">
            {testFeedback && (
              <div
                key={testFeedback.nonce}
                className="animate-toast-in flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-container-highest border border-outline-variant/30 shadow-sm"
              >
                <span
                  className={`material-symbols-outlined text-[18px] ${
                    testFeedback.kind === 'success' ? 'text-green-500' : 'text-error'
                  }`}
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  {testFeedback.kind === 'success' ? 'check_circle' : 'error'}
                </span>
                <span className="text-sm text-on-surface">{testFeedback.text}</span>
              </div>
            )}
            <div className="flex items-center gap-2 bg-surface-container-low/60 border border-outline-variant/30 rounded-lg pl-3 pr-1.5 py-1">
              <label className="text-label-sm text-on-surface-variant uppercase font-bold tracking-wide">
                Últimos
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={testCount}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (Number.isNaN(v)) {
                    setTestCount(1);
                  } else {
                    setTestCount(Math.max(1, Math.min(10, v)));
                  }
                }}
                className="w-12 bg-transparent text-center text-sm font-body-md outline-none focus:ring-2 focus:ring-secondary/30 rounded-md py-1 text-on-surface"
              />
              <span className="text-label-sm text-on-surface-variant pr-1">video(s)</span>
            </div>
            <AnimatedTestButton state={testState} onClick={handleTestNotify} />
            <AnimatedSaveButton saveState={saveState} onSave={handleSave} />
          </div>
        </div>
      </div>

      <ChannelAddedToast
        channelName={toastChannel}
        onDismiss={() => setToastChannel(null)}
      />
    </section>
  );
}
