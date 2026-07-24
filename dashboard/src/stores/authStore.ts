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
