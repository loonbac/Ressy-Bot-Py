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
} from '@/api/youtube';

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={
        'w-10 h-5 rounded-full relative transition-colors duration-300 ' +
        (checked ? 'bg-secondary' : 'bg-outline-variant/30')
      }
    >
      <span
        className={
          'absolute top-1 w-3 h-3 bg-white rounded-full transition-all duration-300 ' +
          (checked ? 'right-1 shadow-sm' : 'left-1 shadow-sm')
        }
      />
    </button>
  );
}

export default function YouTubeConfig() {
  const [subscriptions, setSubscriptions] = useState<YouTubeSubscription[]>([]);
  const [config, setConfig] = useState<YouTubeConfigType | null>(null);
  const [savedConfig, setSavedConfig] = useState<YouTubeConfigType | null>(null);
  const [discordChannels, setDiscordChannels] = useState<DiscordChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<YouTubeSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

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
      setSavedConfig(cfg);
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
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Error al agregar canal');
    } finally {
      setSearching(false);
    }
  };

  const handleDeleteChannel = async (channelId: string) => {
    try {
      await removeYouTubeSubscription(channelId);
      setSubscriptions((prev) => prev.filter((s) => s.channel_id !== channelId));
    } catch (err) {
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

  const handleDiscard = () => {
    if (savedConfig) {
      setConfig({ ...savedConfig });
    }
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const updated = await updateYouTubeConfig(config);
      setConfig(updated);
      setSavedConfig(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const updateConfigField = <K extends keyof YouTubeConfigType>(key: K, value: YouTubeConfigType[K]) => {
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
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
                  {subscriptions.map((sub) => (
                    <div
                      key={sub.channel_id}
                      className="flex items-center justify-between p-3 bg-surface/40 rounded-lg border border-outline-variant/10 hover:shadow-md transition-shadow duration-300"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full border-2 border-secondary/20 overflow-hidden flex-shrink-0">
                          {sub.thumbnail_url ? (
                            <img
                              src={getProxiedThumbnailUrl(sub.thumbnail_url)}
                              alt={sub.channel_name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full bg-primary-container/30 flex items-center justify-center text-secondary">
                              <span className="material-symbols-outlined text-[20px]">smart_display</span>
                            </div>
                          )}
                        </div>
                        <div className="min-w-0">
                          <h4 className="font-medium text-on-surface text-sm truncate">{sub.channel_name || sub.channel_id}</h4>
                          <p className="text-label-sm text-on-surface-variant truncate">@{sub.channel_id}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 flex-shrink-0">
                        <div className="flex items-center gap-2">
                          <span className="text-label-sm text-on-surface-variant hidden xl:inline">Notificaciones</span>
                          <ToggleSwitch
                            checked={sub.notifications_enabled}
                            onChange={(enabled) => handleToggleNotifications(sub.channel_id, enabled)}
                          />
                        </div>
                        <button
                          onClick={() => handleDeleteChannel(sub.channel_id)}
                          className="text-outline hover:text-error transition-colors p-1"
                          aria-label="Eliminar canal"
                        >
                          <span className="material-symbols-outlined text-[20px]">delete</span>
                        </button>
                      </div>
                    </div>
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
          <aside className="col-span-12 lg:col-span-5 flex flex-col gap-4 min-h-0 overflow-y-auto">
            {/* Message Settings Card */}
            <div className="bg-primary-fixed/20 backdrop-blur-md rounded-xl p-5 border border-primary-container/30">
              <h3 className="font-headline-md text-headline-md mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-secondary text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                  forum
                </span>
                Ajustes de Mensaje
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-label-sm text-primary font-bold uppercase mb-1.5">
                    Mensaje de anuncio
                  </label>
                  <textarea
                    className="w-full bg-white/50 border border-outline-variant/20 rounded-lg p-3 text-sm font-body-md h-20 focus:ring-2 focus:ring-secondary/20 outline-none resize-none transition-all"
                    placeholder="@everyone ¡Hay un nuevo video en {canal}!"
                    value={config?.announcement_message ?? ''}
                    onChange={(e) => updateConfigField('announcement_message', e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-label-sm text-primary font-bold uppercase mb-1.5">
                    Canal de Discord
                  </label>
                  <div className="relative">
                    <select
                      className="w-full appearance-none bg-white/50 border border-outline-variant/20 rounded-lg p-3 text-sm font-body-md focus:ring-2 focus:ring-secondary/20 outline-none cursor-pointer"
                      value={config?.discord_channel_id ?? ''}
                      onChange={(e) =>
                        updateConfigField('discord_channel_id', e.target.value ? Number(e.target.value) : null)
                      }
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

            {/* Content Filters Card */}
            <div className="bg-surface-container-lowest/60 backdrop-blur-md rounded-xl p-5 border border-white/40 shadow-sm">
              <h3 className="font-headline-md text-headline-md mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-secondary text-[20px]">filter_list</span>
                Filtros de Contenido
              </h3>
              <div className="space-y-3">
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
            <div className="bg-surface-container-lowest/60 backdrop-blur-md rounded-xl p-5 border border-white/40 shadow-sm">
              <h3 className="font-headline-md text-headline-md mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-secondary text-[20px]">link</span>
                Conexión
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-label-sm text-primary font-bold uppercase mb-1.5">
                    URL de Callback
                  </label>
                  <input
                    type="url"
                    className="w-full bg-white/50 border border-outline-variant/20 rounded-lg p-3 text-sm font-body-md focus:ring-2 focus:ring-secondary/20 outline-none transition-all"
                    placeholder="https://tu-dominio.ngrok-free.app"
                    value={config?.callback_url ?? ''}
                    onChange={(e) => updateConfigField('callback_url', e.target.value)}
                  />
                  <p className="text-tertiary text-xs mt-1">URL pública para recibir notificaciones de YouTube vía PubSubHubbub</p>
                </div>
                <div>
                  <label className="block text-label-sm text-primary font-bold uppercase mb-1.5">
                    Google API Key
                  </label>
                  <input
                    type="password"
                    className="w-full bg-white/50 border border-outline-variant/20 rounded-lg p-3 text-sm font-body-md focus:ring-2 focus:ring-secondary/20 outline-none transition-all"
                    placeholder="AIzaSy..."
                    value={config?.google_api_key ?? ''}
                    onChange={(e) => updateConfigField('google_api_key', e.target.value)}
                  />
                  <p className="text-tertiary text-xs mt-1">Clave de API de YouTube Data API v3 (opcional)</p>
                </div>
              </div>
            </div>
          </aside>

          {/* Footer Actions — slim, part of the grid */}
          <div className="col-span-12 flex justify-end items-center gap-4 py-3 px-5 bg-surface-container-low/40 rounded-xl border border-outline-variant/10 flex-shrink-0">
            <button
              onClick={handleDiscard}
              className="text-on-surface-variant font-medium text-sm hover:text-secondary transition-colors"
            >
              Descartar
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-secondary text-white px-8 py-2.5 rounded-lg font-label-sm shadow-lg hover:scale-[1.02] transition-all duration-300 flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100 bloom-btn"
            >
              <span className="material-symbols-outlined text-[18px]">save</span>
              {saving ? 'Guardando...' : 'Guardar Cambios'}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
