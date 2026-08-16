/**
 * @file authStore.ts
 * @description Zustand store for authentication state. Manages JWT tokens
 * (access + refresh), the current user profile, and the active farm selection.
 * Persisted to localStorage so sessions survive page reloads.
 *
 * State:
 * - `user` — Authenticated user profile (null when logged out)
 * - `token` — JWT access token for API requests
 * - `refreshToken` — JWT refresh token for silent re-auth
 * - `currentFarm` — Currently selected farm ID for multi-farm RBAC scoping
 *
 * Actions:
 * - `login(email, password)` — Authenticate and store tokens
 * - `logout()` — Clear all auth state
 * - `switchFarm(farmId)` — Change the active farm context
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient } from '@/api/client';

interface User {
  id: string;
  email: string;
  fullName: string;
  role: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  currentFarm: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  switchFarm: (farmId: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      refreshToken: null,
      currentFarm: null,

      login: async (email: string, password: string) => {
        const response = await apiClient.post('/api/auth/login', {
          email,
          password,
        });
        const { access_token, refresh_token } = response.data;
        set({
          token: access_token,
          refreshToken: refresh_token,
          user: { id: '', email, fullName: '', role: 'user' },
        });
      },

      logout: () => {
        set({ user: null, token: null, refreshToken: null, currentFarm: null });
      },

      switchFarm: (farmId: string) => {
        set({ currentFarm: farmId });
      },
    }),
    {
      name: 'livestockguard-auth',
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        user: state.user,
        currentFarm: state.currentFarm,
      }),
    }
  )
);
