import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useWebSocket } from '@/hooks/useWebSocket';


class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: ((this: WebSocket, ev: Event) => void) | null = null;
  onmessage: ((this: WebSocket, ev: MessageEvent) => void) | null = null;
  onclose: ((this: WebSocket, ev: CloseEvent) => void) | null = null;
  onerror: ((this: WebSocket, ev: Event) => void) | null = null;

  constructor(url: string | URL) {
    this.url = String(url);
    MockWebSocket.instances.push(this);
  }

  send() {}
  close() {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose.call(this as unknown as WebSocket, new CloseEvent('close'));
    }
  }

  serverSend(data: string) {
    if (this.onmessage) {
      this.onmessage.call(
        this as unknown as WebSocket,
        new MessageEvent('message', { data })
      );
    }
  }

  serverOpen() {
    this.readyState = WebSocket.OPEN;
    if (this.onopen) {
      this.onopen.call(this as unknown as WebSocket, new Event('open'));
    }
  }
}

describe('useWebSocket', () => {
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    originalWebSocket = globalThis.WebSocket;
    globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    MockWebSocket.instances = [];
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
    vi.useRealTimers();
  });

  it('opens a connection on mount', async () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() => useWebSocket(onMessage));
    expect(MockWebSocket.instances.length).toBe(1);
    MockWebSocket.instances[0].serverOpen();
    await waitFor(() => expect(result.current.connected).toBe(true));
  });

  it('receives messages and calls onMessage', async () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket(onMessage));
    MockWebSocket.instances[0].serverOpen();
    MockWebSocket.instances[0].serverSend(
      JSON.stringify({ event: 'config:updated', key: 'x', value: 1 })
    );
    await waitFor(() => {
      expect(onMessage).toHaveBeenCalledWith(
        expect.objectContaining({ event: 'config:updated', key: 'x', value: 1 })
      );
    });
  });

  it('reconnects on disconnect with exponential backoff', () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket(onMessage));
    expect(MockWebSocket.instances.length).toBe(1);
    MockWebSocket.instances[0].serverOpen();

    MockWebSocket.instances[0].close();
    expect(MockWebSocket.instances[0].readyState).toBe(WebSocket.CLOSED);

    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances.length).toBe(2);
  });

  it('cleans up on unmount', () => {
    const onMessage = vi.fn();
    const { unmount } = renderHook(() => useWebSocket(onMessage));
    expect(MockWebSocket.instances.length).toBe(1);
    unmount();
    expect(MockWebSocket.instances[0].readyState).toBe(WebSocket.CLOSED);
  });
});
