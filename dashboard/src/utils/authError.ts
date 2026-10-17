/**
 * @file authError.ts
 * @description Translate a login/auth failure into a clear, user-facing message.
 *
 * Previously the login page showed "Invalid email or password" for EVERY
 * failure — including the backend being down — which is misleading. This
 * helper distinguishes the cases so the message reflects what actually went
 * wrong.
 */
import axios from 'axios';

export interface AuthErrorMessage {
  message: string;
  /** True when the failure is a network/connectivity issue, not bad credentials. */
  isNetwork: boolean;
}

/**
 * Classify an error thrown during login.
 *  - 401                    → credentials are genuinely wrong.
 *  - no response / network  → server unreachable (down, offline, proxy misconfigured).
 *  - timeout (ECONNABORTED) → server did not respond in time.
 *  - other HTTP status      → surface the server's `detail` or a generic fallback.
 */
export function describeAuthError(err: unknown): AuthErrorMessage {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;

    if (status === 401) {
      return { message: 'Invalid email or password.', isNetwork: false };
    }

    // No response object means the request never reached the server.
    if (!err.response) {
      const timedOut = err.code === 'ECONNABORTED';
      return {
        message: timedOut
          ? 'The server took too long to respond. Check that the backend is running, then try again.'
          : 'Cannot reach the server. Check that the backend is running (e.g. `make start`) and try again.',
        isNetwork: true,
      };
    }

    // Some other HTTP error — prefer the server's detail if present.
    const detail = (err.response.data as { detail?: string } | undefined)?.detail;
    return {
      message: detail || `Sign-in failed (status ${status ?? 'unknown'}). Please try again.`,
      isNetwork: false,
    };
  }

  return { message: 'Something went wrong during sign-in. Please try again.', isNetwork: false };
}
