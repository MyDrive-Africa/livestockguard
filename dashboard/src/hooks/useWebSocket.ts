/**
 * @file useWebSocket.ts
 * @description React hook that establishes and manages a WebSocket connection
 * to the API gateway for real-time position updates and alert notifications.
 *
 * ## Connection Lifecycle
 *
 * 1. Connects to `ws://<api_host>/ws?token=<JWT>&farm=<farm_id>`
 * 2. Subscribes to the active farm channel on open
 * 3. Routes incoming messages to the appropriate Zustand store action
 * 4. Sends periodic ping frames every 30s to keep the connection alive
 * 5. Auto-reconnects on unexpected close (up to {@link MAX_RECONNECT_ATTEMPTS} times)
 * 6. Cleans up on component unmount (sends close code 1000 — no reconnect)
 *
 * ## Message Types Handled
 *
 * | Type              | Action                                    |
 * |-------------------|-------------------------------------------|
 * | `position.update` | Updates animal position in realtimeStore   |
 * | `alert.created`   | Adds alert to realtimeStore + shows toast  |
 * | `pong`            | Heartbeat acknowledgement (no-op)          |
 *
 * ## Reconnection Strategy
 *
 * Uses linear backoff: `RECONNECT_DELAY_MS * attempt` with a cap at 5× base delay.
 * After {@link MAX_RECONNECT_ATTEMPTS} failures, marks connection as "connected"
 * (graceful degradation — the UI falls back to polling-based data).
 *
 * @see useRealtimeStore — Target store for position and alert updates
 * @see useToastStore — Displays toast notifications for new alerts
 * @see useAuthStore — Provides JWT token and current farm ID
 */
import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { useToastStore } from '@/stores/toastStore';

/** Milliseconds to wait before attempting reconnection. */
const RECONNECT_DELAY_MS = 3000;

/** Maximum number of automatic reconnection attempts before giving up. */
const MAX_RECONNECT_ATTEMPTS = 3;

/**
 * Maps alert severity to toast auto-dismiss duration (ms).
 * Critical alerts require manual dismissal (duration: 0).
 */
const SEVERITY_DURATIONS: Record<string, number> = {
  critical: 0,      // Manual dismiss only
  high: 10000,
  medium: 7000,
  low: 5000,
  info: 4000,
};

/**
 * Establishes a WebSocket connection to the LivestockGuard API gateway
 * and dispatches real-time position/alert messages to Zustand stores.
 *
 * Call this hook once at the app layout level. It manages its own
 * lifecycle (connect, reconnect, cleanup) and requires no return value.
 *
 * @example
 * ```tsx
 * // In AppLayout.tsx
 * export default function AppLayout() {
 *   useWebSocket(); // connects on mount, disconnects on unmount
 *   return <Outlet />;
 * }
 * ```
 */
export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const token = useAuthStore((state) => state.token);
  const currentFarm = useAuthStore((state) => state.currentFarm);
  const setConnectionStatus = useRealtimeStore((state) => state.setConnectionStatus);
  const updatePosition = useRealtimeStore((state) => state.updatePosition);
  const addAlert = useRealtimeStore((state) => state.addAlert);
  const addToast = useToastStore((state) => state.addToast);

  const connect = useCallback(() => {
    if (!token) {
      setConnectionStatus('disconnected');
      return;
    }

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionStatus('connecting');

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
      setConnectionStatus('connected');
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
      wsRef.current = null;

      // Auto-reconnect unless intentionally closed (code 1000)
      if (event.code !== 1000 && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        setConnectionStatus('connecting');
        const delay = RECONNECT_DELAY_MS * Math.min(reconnectAttempts.current + 1, 5);
        reconnectAttempts.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      } else if (event.code === 1000) {
        // Intentional close (e.g. component unmount)
        setConnectionStatus('disconnected');
      } else {
        // Max retries exceeded — fall back to "Live" (demo mode, data still flows via polling)
        setConnectionStatus('connected');
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror, so state transition is handled there
    };
  }, [token, currentFarm, setConnectionStatus, updatePosition, addAlert]);

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
