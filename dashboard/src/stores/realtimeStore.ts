import { create } from 'zustand';
import { AnimalPosition, Alert } from '@/types';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';

interface RealtimeState {
  positions: Map<string, AnimalPosition>;
  alerts: Alert[];
  wsConnected: boolean;
  connectionStatus: ConnectionStatus;
  setConnected: (connected: boolean) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  updatePosition: (animalId: string, position: AnimalPosition) => void;
  addAlert: (alert: Alert) => void;
  acknowledgeAlert: (alertId: string) => void;
}

export const useRealtimeStore = create<RealtimeState>((set) => ({
  positions: new Map(),
  alerts: [],
  wsConnected: false,
  connectionStatus: 'connecting',

  setConnected: (connected) => set({
    wsConnected: connected,
    connectionStatus: connected ? 'connected' : 'connecting',
  }),

  setConnectionStatus: (status) => set({
    connectionStatus: status,
    wsConnected: status === 'connected',
  }),

  updatePosition: (animalId, position) =>
    set((state) => {
      const newPositions = new Map(state.positions);
      newPositions.set(animalId, position);
      return { positions: newPositions };
    }),

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 100),
    })),

  acknowledgeAlert: (alertId) =>
    set((state) => ({
      alerts: state.alerts.map((a) =>
        a.id === alertId ? { ...a, status: 'acknowledged' as const } : a
      ),
    })),
}));
