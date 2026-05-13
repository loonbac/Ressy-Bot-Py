import { useState, useCallback, useEffect } from 'react';
import { WebSocketProvider } from '@/context/WebSocketContext';
import DashboardLayout from '@/components/DashboardLayout';
import ConfigPanel from '@/components/ConfigPanel';
import PluginList from '@/components/PluginList';
import SystemStatus from '@/components/SystemStatus';
import YouTubeConfig from '@/components/YouTubeConfig';
import WelcomeConfig from '@/components/WelcomeConfig';
import BlackboardConfig from '@/components/BlackboardConfig';
import { ThemeToggle } from '@/components/ThemeToggle';
import SakuraPetals from '@/components/SakuraPetals';
import { fetchConfig, updateConfig, fetchStatus } from '@/api/config';
import { ConfigResponse, WSMessage, BotStatus } from '@/types';

const sectionTitles: Record<string, string> = {
  config: 'Configuración',
  plugins: 'Plugins',
  status: 'Estado del Sistema',
  youtube: 'YouTube',
  welcome: 'Bienvenida',
  blackboard: 'Blackboard',
};

export default function App() {
  const [activeSection, setActiveSection] = useState('status');
  const [configs, setConfigs] = useState<ConfigResponse[]>([]);
  const [plugins, setPlugins] = useState<string[]>([]);
  const [status, setStatus] = useState<BotStatus | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [cfg, st] = await Promise.all([fetchConfig(), fetchStatus()]);
      setConfigs(cfg);
      setPlugins(st.loaded_cogs);
      setStatus(st);
    } catch {
      // errors are silently ignored; components show stale/empty state
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleUpdate = useCallback(
    async (key: string, value: unknown) => {
      await updateConfig(key, value);
      setConfigs((prev) =>
        prev.map((c) =>
          c.key === key
            ? { ...c, value, updated_at: new Date().toISOString() }
            : c
        )
      );
    },
    []
  );

  const handleMessage = useCallback((msg: WSMessage) => {
    if (msg.event === 'config:updated') {
      setConfigs((prev) =>
        prev.map((c) =>
          c.key === msg.key
            ? { ...c, value: msg.value, updated_at: new Date().toISOString() }
            : c
        )
      );
    } else if (msg.event === 'config:deleted') {
      setConfigs((prev) => prev.filter((c) => c.key !== msg.key));
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const st = await fetchStatus();
        setStatus(st);
        setPlugins(st.loaded_cogs);
      } catch {
        // ignore
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <WebSocketProvider onMessage={handleMessage}>
      <SakuraPetals />
      <ThemeToggle />
      <DashboardLayout
        title={sectionTitles[activeSection] ?? 'Ressy Bot'}
        activeSection={activeSection}
        onNavigate={setActiveSection}
        botAvatarUrl={status?.bot_avatar_url}
        botName={status?.bot_name}
      >
        {activeSection === 'config' && (
          <ConfigPanel configs={configs} onUpdate={handleUpdate} status={status} />
        )}
        {activeSection === 'plugins' && <PluginList plugins={plugins} onNavigate={setActiveSection} />}
        {activeSection === 'status' && <SystemStatus status={status} />}
        {activeSection === 'youtube' && (
          <YouTubeConfig
            botName={status?.bot_name}
            botAvatarUrl={status?.bot_avatar_url}
            onNavigate={setActiveSection}
          />
        )}
        {activeSection === 'welcome' && (
          <WelcomeConfig
            onNavigate={setActiveSection}
            botName={status?.bot_name}
            botAvatarUrl={status?.bot_avatar_url}
          />
        )}
        {activeSection === 'blackboard' && (
          <BlackboardConfig
            onNavigate={setActiveSection}
            botName={status?.bot_name}
            botAvatarUrl={status?.bot_avatar_url}
          />
        )}
      </DashboardLayout>
    </WebSocketProvider>
  );
}
