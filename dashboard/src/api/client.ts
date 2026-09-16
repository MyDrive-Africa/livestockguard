import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

export const apiClient = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
apiClient.interceptors.request.use((config) => {
  const stored = localStorage.getItem('livestockguard-auth');
  if (stored) {
    try {
      const { state } = JSON.parse(stored);
      if (state?.token) {
        config.headers.Authorization = `Bearer ${state.token}`;
      }
    } catch {
      // Ignore parse errors
    }
  }
  return config;
});

/**
 * Single-flight refresh coordination.
 *
 * When several requests 401 at once (e.g. the Map page fires many calls on
 * mount), we must only hit /api/auth/refresh ONCE. The first 401 kicks off the
 * refresh; concurrent 401s await the same promise, then retry with the new
 * token. Because the backend rotates refresh tokens, a second parallel refresh
 * would 401 on the now-blacklisted token and needlessly log the user out.
 */
let refreshPromise: Promise<string> | null = null;

function forceLogout() {
  localStorage.removeItem('livestockguard-auth');
  window.location.href = '/login';
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;

    const status = error.response?.status;
    const url = originalRequest?.url ?? '';

    // Don't try to refresh for the auth endpoints themselves (login/refresh):
    // a 401 there is a genuine credential failure.
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh');

    if (status === 401 && originalRequest && !originalRequest._retry && !isAuthEndpoint) {
      originalRequest._retry = true;

      try {
        if (!refreshPromise) {
          // Lazy import avoids a circular module-load dependency
          // (authStore imports apiClient).
          refreshPromise = import('@/stores/authStore').then(({ useAuthStore }) =>
            useAuthStore.getState().refresh()
          );
        }
        const newToken = await refreshPromise;
        refreshPromise = null;

        // Retry the original request with the refreshed token.
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed (expired/revoked refresh token) — genuinely logged out.
        refreshPromise = null;
        forceLogout();
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
