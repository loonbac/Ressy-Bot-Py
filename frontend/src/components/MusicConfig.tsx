import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ALL_COMMANDS,
  fetchMusicConfig,
  fetchMusicNowPlaying,
  fetchMusicQueue,
  fetchMusicVoiceChannels,
  updateMusicConfig,
  type MusicConfig as MusicConfigType,
  type MusicNowPlaying,
  type MusicQueueResponse,
  type MusicVoiceChannel,
} from '@/api/music';
import { fetchConfig, fetchGuilds } from '@/api/config';
import PageHeader from './music/PageHeader';
import PlaybackSettingsCard from './music/PlaybackSettingsCard';
import AllowedChannelsCard from './music/AllowedChannelsCard';
import CommandsPanel from './music/CommandsPanel';
import QueueCard from './music/QueueCard';
import TurntableCard from './music/TurntableCard';
import FooterActions, { type SaveState } from './music/FooterActions';
import './music/animations.css';
import './music/CommandsPanel.css';

interface Feedback {
  kind: 'success' | 'error';
  text: string;
  nonce: number;
}

interface Props {
  onNavigate?: (section: string) => void;
}

const POLL_INTERVAL_MS = 1500;

export default function MusicConfig({ onNavigate }: Props) {
  const [config, setConfig] = useState<MusicConfigType | null>(null);
  const [originalConfig, setOriginalConfig] = useState<MusicConfigType | null>(null);
  const [channels, setChannels] = useState<MusicVoiceChannel[]>([]);
  const [guildId, setGuildId] = useState<string>('');
  const [guildName, setGuildName] = useState<string>('');
  const [nowPlaying, setNowPlaying] = useState<MusicNowPlaying | null>(null);
  const [queue, setQueue] = useState<MusicQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [commandsPanelOpen, setCommandsPanelOpen] = useState(false);

  const guildIdRef = useRef<string>('');
  guildIdRef.current = guildId;

  const loadStaticData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, chs, globalCfg, gs] = await Promise.all([
        fetchMusicConfig(),
        fetchMusicVoiceChannels(),
        fetchConfig(),
        fetchGuilds(),
      ]);
      setConfig(cfg);
      setOriginalConfig(cfg);
      setChannels(chs);
      const guildIdEntry = globalCfg.find((c) => c.key === 'guild_id');
      const resolvedGuildId =
        typeof guildIdEntry?.value === 'string' ? guildIdEntry.value : '';
      setGuildId(resolvedGuildId);
      const matched = gs.find((g) => g.id === resolvedGuildId);
      setGuildName(matched?.name ?? '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar datos');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStaticData();
  }, [loadStaticData]);

  // Poll now playing + queue for the configured guild — pause when tab hidden
  useEffect(() => {
    if (!guildId) {
      setNowPlaying(null);
      setQueue(null);
      return;
    }
    let cancelled = false;
    let timerId: number | null = null;

    const poll = async () => {
      try {
        const [np, q] = await Promise.all([
          fetchMusicNowPlaying(guildId),
          fetchMusicQueue(guildId),
        ]);
        if (!cancelled && guildIdRef.current === guildId) {
          setNowPlaying(np);
          setQueue(q);
        }
      } catch {
        /* ignore polling errors */
      }
    };

    const start = () => {
      if (timerId !== null) return;
      poll();
      timerId = window.setInterval(poll, POLL_INTERVAL_MS);
    };

    const stop = () => {
      if (timerId !== null) {
        window.clearInterval(timerId);
        timerId = null;
      }
    };

    const handleVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        start();
      }
    };

    if (!document.hidden) start();
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      cancelled = true;
      stop();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [guildId]);

  const updateField = <K extends keyof MusicConfigType>(
    key: K,
    value: MusicConfigType[K],
  ) => {
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const showFeedback = (kind: 'success' | 'error', text: string) => {
    setFeedback({ kind, text, nonce: Date.now() });
    window.setTimeout(() => {
      setFeedback((prev) => (prev && prev.text === text ? null : prev));
    }, 4200);
  };

  const dirty = useMemo(() => {
    if (!config || !originalConfig) return false;
    return JSON.stringify(config) !== JSON.stringify(originalConfig);
  }, [config, originalConfig]);

  const handleSave = async () => {
    if (!config) return;
    setSaveState('saving');
    try {
      const updated = await updateMusicConfig(config);
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

  if (loading) {
    return (
      <section className="fixed top-20 bottom-0 left-64 right-0 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined text-4xl text-secondary animate-spin">
            progress_activity
          </span>
          <p className="text-on-surface-variant font-body-md">
            Cargando configuración de música...
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
            onClick={loadStaticData}
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
      aria-label="Configuración de Música"
      className="fixed top-20 bottom-0 left-64 right-0 px-margin-desktop py-4 overflow-hidden"
    >
      <div className="max-w-container-max mx-auto h-full grid grid-rows-[auto_minmax(0,1fr)_auto] gap-3 overflow-hidden">
        <div className="flex items-center justify-between gap-3 flex-shrink-0">
          <PageHeader onBack={() => onNavigate?.('plugins')} />
          <button
            type="button"
            onClick={() => setCommandsPanelOpen(true)}
            className="music-commands-trigger"
            aria-label="Abrir panel de comandos"
          >
            <span
              className="material-symbols-outlined text-[16px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              terminal
            </span>
            <span>Comandos</span>
            <span className="music-commands-trigger__badge">
              {config?.enabled_commands.length ?? 0}/{ALL_COMMANDS.length}
            </span>
            <span className="material-symbols-outlined text-[16px]">chevron_left</span>
          </button>
        </div>

        {error && (
          <div className="p-2.5 bg-error-container/50 border border-error/20 rounded-lg flex items-center gap-3 text-error">
            <span className="material-symbols-outlined text-[18px]">error</span>
            <span className="font-body-md text-sm">{error}</span>
          </div>
        )}

        <div
          className="grid grid-cols-12 gap-3 min-h-0 overflow-hidden"
          style={{
            gridTemplateRows: 'minmax(0, 5fr) minmax(0, 4fr)',
          }}
        >
          {/* Row 1: Turntable (visual hero, 8) | Queue (4) */}
          <div className="col-span-12 lg:col-span-8 min-h-0 overflow-hidden animate-music-card-enter animate-music-card-stagger-1">
            <TurntableCard nowPlaying={nowPlaying} guildName={guildName} />
          </div>
          <div className="col-span-12 lg:col-span-4 min-h-0 overflow-hidden animate-music-card-enter animate-music-card-stagger-2">
            <QueueCard queue={queue} />
          </div>

          {/* Row 2: Playback (6) | Channels (6) — Commands movido al panel lateral */}
          <div className="col-span-12 lg:col-span-6 min-h-0 overflow-hidden animate-music-card-enter animate-music-card-stagger-3">
            <PlaybackSettingsCard config={config} onChange={updateField} />
          </div>
          <div className="col-span-12 lg:col-span-6 min-h-0 overflow-hidden animate-music-card-enter animate-music-card-stagger-4">
            <AllowedChannelsCard config={config} channels={channels} onChange={updateField} />
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

      <CommandsPanel
        open={commandsPanelOpen}
        config={config}
        onClose={() => setCommandsPanelOpen(false)}
        onChange={updateField}
      />
    </section>
  );
}
