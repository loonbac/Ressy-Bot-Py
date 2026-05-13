import { useCallback, useEffect, useState } from 'react';
import {
  fetchWelcomeConfig,
  fetchWelcomeDiscordChannels,
  sendWelcomeTest,
  updateWelcomeConfig,
  type WelcomeConfig as WelcomeConfigType,
  type WelcomeDiscordChannel,
} from '@/api/welcome';
import PageHeader from './welcome/PageHeader';
import BasicSettingsCard from './welcome/BasicSettingsCard';
import './welcome/animations.css';
import ImageCard from './welcome/ImageCard';
import ColorPickerCard from './welcome/ColorPickerCard';
import PreviewCard from './welcome/PreviewCard';
import AdvancedCard from './welcome/AdvancedCard';
import FooterActions, {
  type SaveState,
  type TestState,
} from './welcome/FooterActions';

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

export default function WelcomeConfig({ onNavigate, botName, botAvatarUrl }: Props) {
  const [config, setConfig] = useState<WelcomeConfigType | null>(null);
  const [channels, setChannels] = useState<WelcomeDiscordChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [testState, setTestState] = useState<TestState>('idle');
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, chs] = await Promise.all([
        fetchWelcomeConfig(),
        fetchWelcomeDiscordChannels(),
      ]);
      setConfig(cfg);
      setChannels(chs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar configuración');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const updateField = <K extends keyof WelcomeConfigType>(
    key: K,
    value: WelcomeConfigType[K],
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
      const updated = await updateWelcomeConfig(config);
      setConfig(updated);
      setSaveState('success');
      showFeedback('success', 'Configuración guardada');
      window.setTimeout(() => setSaveState('idle'), 1800);
    } catch (err) {
      setSaveState('error');
      showFeedback('error', err instanceof Error ? err.message : 'Error al guardar');
      window.setTimeout(() => setSaveState('idle'), 1800);
    }
  };

  const handleTest = async () => {
    if (!config) return;
    setTestState('testing');
    try {
      const updated = await updateWelcomeConfig(config);
      setConfig(updated);
      const result = await sendWelcomeTest();
      setTestState('success');
      showFeedback('success', `Mensaje de prueba enviado al canal ${result.channel_id}`);
      window.setTimeout(() => setTestState('idle'), 1800);
    } catch (err) {
      setTestState('error');
      showFeedback('error', err instanceof Error ? err.message : 'Error al enviar prueba');
      window.setTimeout(() => setTestState('idle'), 1800);
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
            Cargando configuración de bienvenida...
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
      aria-label="Configuración de Bienvenida"
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
          style={{ gridTemplateRows: 'minmax(0, 3fr) minmax(0, 2fr)' }}
        >
          {/* Row 1: Editor (left, larger) | Preview (right) */}
          <div className="col-span-12 lg:col-span-7 min-h-0 overflow-hidden animate-welcome-card-enter animate-welcome-card-stagger-1">
            <BasicSettingsCard config={config} channels={channels} onChange={updateField} />
          </div>
          <div className="col-span-12 lg:col-span-5 min-h-0 overflow-hidden animate-welcome-card-enter animate-welcome-card-stagger-2">
            <PreviewCard config={config} botName={botName} botAvatarUrl={botAvatarUrl} />
          </div>

          {/* Row 2: Image (3) | Color (5, wider) | Advanced (4, narrower) */}
          <div className="col-span-12 lg:col-span-3 min-h-0 overflow-hidden animate-welcome-card-enter animate-welcome-card-stagger-3">
            <ImageCard config={config} onChange={updateField} />
          </div>
          <div className="col-span-12 lg:col-span-5 min-h-0 overflow-hidden animate-welcome-card-enter animate-welcome-card-stagger-4">
            <ColorPickerCard config={config} onChange={updateField} />
          </div>
          <div className="col-span-12 lg:col-span-4 min-h-0 overflow-hidden animate-welcome-card-enter animate-welcome-card-stagger-5">
            <AdvancedCard config={config} onChange={updateField} />
          </div>
        </div>

        <FooterActions
          saveState={saveState}
          testState={testState}
          feedback={feedback}
          onSave={handleSave}
          onTest={handleTest}
        />
      </div>
    </section>
  );
}
