/**
 * API client for LivestockGuard mobile app.
 * Same endpoints as the web dashboard.
 */

import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { Platform } from 'react-native';

// Android emulator uses 10.0.2.2 to reach host machine's localhost
// iOS simulator can use localhost directly
const API_BASE_URL = __DEV__
  ? Platform.OS === 'android'
    ? 'http://10.0.2.2:8000'
    : 'http://localhost:8000'
  : 'https://api.livestockguard.co.za';

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
