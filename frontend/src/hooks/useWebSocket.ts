import { useEffect, useRef, useState, useCallback } from 'react';
import { WSMessage } from '@/types';

export interface UseWebSocketReturn {
  connected: boolean;
  reconnecting: boolean;
}

export function useWebSocket(
  onMessage: (msg: WSMessage) => void
): UseWebSocketReturn {
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptRef = useRef(0);
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    if (wsRef.current) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setReconnecting(false);
      attemptRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage;
        onMessageRef.current(msg);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (wsRef.current === ws) {
        setConnected(false);
        wsRef.current = null;
      }
      attemptRef.current += 1;
      const delay = Math.min(30000, 1000 * 2 ** (attemptRef.current - 1));
      setReconnecting(true);
      timeoutRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      if (wsRef.current) {
        const ws = wsRef.current;
        wsRef.current = null;
        ws.onclose = null;
        ws.close();
      }
    };
  }, [connect]);

  return { connected, reconnecting };
}
