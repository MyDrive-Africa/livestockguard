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
 * - `refresh()` — Exchange the stored refresh token for a fresh access token
 * - `logout()` — Clear all auth state
 * - `switchFarm(farmId)` — Change the active farm context
 */
import axios from 'axios';
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
  refresh: () => Promise<string>;
  logout: () => void;
  switchFarm: (farmId: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
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

      refresh: async (): Promise<string> => {
        const currentRefreshToken = get().refreshToken;
        if (!currentRefreshToken) {
          throw new Error('No refresh token available');
        }
        // Use a bare axios instance (not apiClient) so the 401 response
        // interceptor cannot recurse into this refresh call.
        const response = await axios.post('/api/auth/refresh', {
          refresh_token: currentRefreshToken,
        });
        const { access_token, refresh_token } = response.data;
        // The backend rotates refresh tokens (old one is blacklisted), so we
        // MUST store the newly issued refresh_token for the next refresh.
        set({ token: access_token, refreshToken: refresh_token });
        return access_token;
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
