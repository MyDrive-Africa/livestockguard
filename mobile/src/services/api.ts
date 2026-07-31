/**
 * API client for LivestockGuard mobile app.
 * Same endpoints as the web dashboard.
 */

import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { Platform } from 'react-native';
import Constants from 'expo-constants';

// Determine API URL:
// - In dev: Android emulator uses 10.0.2.2, iOS uses localhost
//   If running via QEMU or non-standard emulator, the debuggerHost
//   from Expo gives us the actual Metro host IP which also works for the API.
// - In prod: use the production URL
function getApiBaseUrl(): string {
  if (!__DEV__) return 'https://api.livestockguard.co.za';

  // Expo provides the host IP that Metro is running on — works for any emulator
  const debuggerHost = Constants.expoConfig?.hostUri
    ?? Constants.manifest2?.extra?.expoGo?.debuggerHost
    ?? (Constants as any).manifest?.debuggerHost;

  if (debuggerHost) {
    const hostIp = debuggerHost.split(':')[0];
    return `http://${hostIp}:8000`;
  }

  // Fallback: standard emulator mappings
  if (Platform.OS === 'android') return 'http://10.0.2.2:8000';
  return 'http://localhost:8000';
}

const API_BASE_URL = getApiBaseUrl();

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

// Attach auth token to every request
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses — clear stale tokens so the app returns to login
let logoutCallback: (() => void) | null = null;

export function setLogoutCallback(cb: () => void) {
  logoutCallback = cb;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid — clear stored auth and trigger logout
      await AsyncStorage.removeItem('auth_token');
      await AsyncStorage.removeItem('user_role');
      if (logoutCallback) logoutCallback();
    }
    return Promise.reject(error);
  }
);

// Auth functions
export async function login(email: string, password: string) {
  const resp = await api.post('/api/auth/login', { email, password });
  const { access_token, user } = resp.data;
  await AsyncStorage.setItem('auth_token', access_token);
  await AsyncStorage.setItem('user_role', user?.role || 'viewer');
  return resp.data;
}

export async function logout() {
  await AsyncStorage.removeItem('auth_token');
  await AsyncStorage.removeItem('user_role');
}

export async function getToken() {
  return AsyncStorage.getItem('auth_token');
}

export async function getUserRole() {
  return AsyncStorage.getItem('user_role');
}
