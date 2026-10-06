import { useState, useEffect, useRef, useCallback } from 'react';
import type { ConnectionStatus, WSEvent } from '../types';

export const useWebSocket = (url: string) => {
  const [status, setStatus] = useState<ConnectionStatus>('DISCONNECTED');
  const [events, setEvents] = useState<WSEvent[]>([]);
  const ws = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    setStatus('CONNECTING');
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      setStatus('CONNECTED');
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents((prev) => [data, ...prev].slice(0, 100)); // keep last 100 events
    };

    ws.current.onclose = () => {
      setStatus('DISCONNECTED');
      // Reconnect logic
      setTimeout(() => {
        setStatus('RECONNECTING');
        connect();
      }, 2000);
    };

    ws.current.onerror = () => {
      // It will trigger onclose after
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [connect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return { status, events, clearEvents };
};
