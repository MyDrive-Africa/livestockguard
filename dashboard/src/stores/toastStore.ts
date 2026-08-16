/**
 * @file toastStore.ts
 * @description Zustand store for ephemeral toast notifications. Manages a capped
 * queue of up to 10 visible toasts with severity-based styling and auto-dismiss.
 *
 * State:
 * - `toasts` — Array of active toast notifications (max 10)
 *
 * Actions:
 * - `addToast(toast)` — Add a notification (auto-generates ID and timestamp)
 * - `removeToast(id)` — Dismiss a specific toast
 * - `clearAll()` — Remove all toasts at once
 *
 * Auto-dismiss: Toasts with `duration > 0` are automatically removed after the
 * specified milliseconds. Set `duration: 0` for persistent toasts that require
 * manual dismissal.
 */
import { create } from 'zustand';

export type ToastSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info' | 'success';

export interface Toast {
  id: string;
  title: string;
  message: string;
  severity: ToastSeverity;
  timestamp: number;
  /** Auto-dismiss after this many ms (0 = manual dismiss only) */
  duration: number;
}

interface ToastState {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id' | 'timestamp'>) => void;
  removeToast: (id: string) => void;
  clearAll: () => void;
}

let counter = 0;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (toast) => {
    const id = `toast-${++counter}-${Date.now()}`;
    const newToast: Toast = {
      ...toast,
      id,
      timestamp: Date.now(),
    };
    set((state) => ({
      toasts: [...state.toasts, newToast].slice(-10), // Max 10 visible
    }));

    // Auto-dismiss after duration
    if (toast.duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, toast.duration);
    }
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),

  clearAll: () => set({ toasts: [] }),
}));
