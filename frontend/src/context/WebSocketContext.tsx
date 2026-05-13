import { createContext, useContext, ReactNode } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { WSMessage } from '@/types';

interface WebSocketContextValue {
  connected: boolean;
  reconnecting: boolean;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export function WebSocketProvider({
  children,
  onMessage,
}: {
  children: ReactNode;
  onMessage: (msg: WSMessage) => void;
}) {
  const { connected, reconnecting } = useWebSocket(onMessage);
  return (
    <WebSocketContext.Provider value={{ connected, reconnecting }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error(
      'useWebSocketContext must be used inside a WebSocketProvider'
    );
  }
  return ctx;
}
