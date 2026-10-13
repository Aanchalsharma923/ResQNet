import { useState, useEffect, useRef, useCallback } from 'react';
import type { ConnectionStatus, WSEvent } from '../types';

let localEventCounter = 0;

export const useWebSocket = (url: string) => {
  const [status, setStatus] = useState<ConnectionStatus>('DISCONNECTED');
  const [events, setEvents] = useState<WSEvent[]>([]);
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const isUnmountedRef = useRef<boolean>(false);

  const connect = useCallback(() => {
    if (isUnmountedRef.current) return;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (ws.current) {
      // Avoid creating multiple sockets
      try {
        ws.current.close();
      } catch {
        // ignore error on existing socket close
      }
    }

    setStatus('CONNECTING');
    const socket = new WebSocket(url);
    ws.current = socket;

    socket.onopen = () => {
      if (isUnmountedRef.current) {
        socket.close();
        return;
      }
      setStatus('CONNECTED');
    };

    socket.onmessage = (event) => {
      if (isUnmountedRef.current) return;

      try {
        const data = JSON.parse(event.data) as WSEvent;

        if (!data.event_id) {
          localEventCounter += 1;
          data.event_id = `local-${localEventCounter}`;
        }

        // Provide a fallback timestamp if missing
        if (!data.timestamp) {
          data.timestamp = new Date().toISOString();
        }

        setEvents((prev) => {
          if (prev.some((e) => e.event_id === data.event_id)) {
            return prev;
          }
          // INITIAL_STATE is a state synchronization handshake sent upon client connect.
          // Replace any older INITIAL_STATE so reconnected handshakes don't stack redundantly.
          if (data.type === 'INITIAL_STATE') {
            const nonInitial = prev.filter(e => e.type !== 'INITIAL_STATE');
            return [data, ...nonInitial].slice(0, 100);
          }
          return [data, ...prev].slice(0, 100);
        });
      } catch (err) {
        console.error('Failed to parse WebSocket event:', err);
      }
    };

    socket.onclose = () => {
      if (isUnmountedRef.current) return;
      setStatus('DISCONNECTED');
      // Reconnect logic
      reconnectTimeoutRef.current = window.setTimeout(() => {
        if (!isUnmountedRef.current) {
          setStatus('RECONNECTING');
          connect();
        }
      }, 2000);
    };

    socket.onerror = () => {
      // It will trigger onclose after
    };
  }, [url]);

  useEffect(() => {
    isUnmountedRef.current = false;
    connect();
    return () => {
      isUnmountedRef.current = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (ws.current) {
        ws.current.close();
        ws.current = null;
      }
    };
  }, [connect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return { status, events, clearEvents };
};
