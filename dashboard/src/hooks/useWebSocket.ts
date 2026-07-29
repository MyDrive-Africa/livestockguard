import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { useToastStore } from '@/stores/toastStore';

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

const SEVERITY_DURATIONS: Record<string, number> = {
  critical: 0,      // Manual dismiss only
  high: 10000,
  medium: 7000,
  low: 5000,
  info: 4000,
};

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const token = useAuthStore((state) => state.token);
  const currentFarm = useAuthStore((state) => state.currentFarm);
  const setConnected = useRealtimeStore((state) => state.setConnected);
  const updatePosition = useRealtimeStore((state) => state.updatePosition);
  const addAlert = useRealtimeStore((state) => state.addAlert);
  const addToast = useToastStore((state) => state.addToast);

  const connect = useCallback(() => {
    if (!token) return;

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // In development, WebSocket connects to API server (port 8000), not Vite dev server
    const apiHost = window.location.port === '5173' || window.location.port === '5174' || window.location.port === '5175'
      ? `${window.location.hostname}:8000`
      : window.location.host;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const farmParam = currentFarm ? `&farm=${currentFarm}` : '';
    const wsUrl = `${protocol}//${apiHost}/ws?token=${token}${farmParam}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectAttempts.current = 0;
      // Subscribe to farm channel
      ws.send(JSON.stringify({ type: 'subscribe', channel: `farm:${currentFarm}` }));
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        switch (message.type) {
          case 'position.update':
            updatePosition(message.payload.animalId, {
              animalId: message.payload.animalId,
              animalName: message.payload.animalName,
              position: message.payload.position,
              activityState: message.payload.activityState,
              batteryLevel: message.payload.batteryLevel,
            });
            break;

          case 'alert.created':
            addAlert(message.payload);
            addToast({
              title: message.payload.alert_type?.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()) || 'Alert',
              message: message.payload.message || `${message.payload.animal_name || 'Unknown animal'} — ${message.payload.severity}`,
              severity: message.payload.severity || 'high',
              duration: SEVERITY_DURATIONS[message.payload.severity] ?? 7000,
            });
            break;

          case 'pong':
            // Heartbeat response, connection is alive
            break;
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = (event) => {
      setConnected(false);
      wsRef.current = null;

      // Auto-reconnect unless intentionally closed (code 1000)
      if (event.code !== 1000 && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = RECONNECT_DELAY_MS * Math.min(reconnectAttempts.current + 1, 5);
        reconnectAttempts.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      setConnected(false);
    };
  }, [token, currentFarm, setConnected, updatePosition, addAlert]);

  useEffect(() => {
    connect();

    // Send periodic pings to keep connection alive
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close(1000); // Normal closure, don't reconnect
        wsRef.current = null;
      }
    };
  }, [connect]);
}
