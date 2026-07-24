import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useRealtimeStore } from '@/stores/realtimeStore';

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const token = useAuthStore((state) => state.token);
  const currentFarm = useAuthStore((state) => state.currentFarm);
  const setConnected = useRealtimeStore((state) => state.setConnected);
  const updatePosition = useRealtimeStore((state) => state.updatePosition);
  const addAlert = useRealtimeStore((state) => state.addAlert);

  useEffect(() => {
    if (!token || !currentFarm) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws?token=${token}&farm=${currentFarm}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
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
            break;
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };

    ws.onerror = () => {
      setConnected(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [token, currentFarm, setConnected, updatePosition, addAlert]);
}
