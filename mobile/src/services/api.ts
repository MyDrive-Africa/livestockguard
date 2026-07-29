/**
 * API client for LivestockGuard mobile app.
 * Same endpoints as the web dashboard.
 */

import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

// In dev, point to local API. In production, use the deployed URL.
const API_BASE_URL = __DEV__
  ? 'http://192.168.1.100:8000'  // Replace with your machine's local IP
  : 'https://api.livestockguard.co.za';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

// Attach auth token to every request
api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth functions
export async function login(email: string, password: string) {
  const resp = await api.post('/api/auth/login', { email, password });
  const { access_token, user } = resp.data;
  await SecureStore.setItemAsync('auth_token', access_token);
  await SecureStore.setItemAsync('user_role', user?.role || 'viewer');
  return resp.data;
}

export async function logout() {
  await SecureStore.deleteItemAsync('auth_token');
  await SecureStore.deleteItemAsync('user_role');
}

export async function getToken() {
  return SecureStore.getItemAsync('auth_token');
}

export async function getUserRole() {
  return SecureStore.getItemAsync('user_role');
}
