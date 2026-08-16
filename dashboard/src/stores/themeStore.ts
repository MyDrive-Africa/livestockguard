/**
 * @file themeStore.ts
 * @description Zustand store for colour theme management. Supports light, dark,
 * and system (auto-detect from OS preference) modes. Applies the `dark` class
 * to `<html>` for Tailwind's `darkMode: 'class'` strategy. Persisted to localStorage.
 *
 * State:
 * - `theme` — User's selected preference ('light' | 'dark' | 'system')
 * - `resolved` — Actual applied theme after resolving 'system' to a concrete value
 *
 * Actions:
 * - `setTheme(theme)` — Update preference, persist, and apply to DOM immediately
 *
 * Also listens to `prefers-color-scheme` media query changes to update
 * automatically when the user switches their OS theme while in 'system' mode.
 */
import { create } from 'zustand';

export type Theme = 'light' | 'dark' | 'system';

interface ThemeState {
  theme: Theme;
  resolved: 'light' | 'dark';
  setTheme: (theme: Theme) => void;
}

function getSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function resolveTheme(theme: Theme): 'light' | 'dark' {
  return theme === 'system' ? getSystemTheme() : theme;
}

function applyThemeToDOM(resolved: 'light' | 'dark') {
  const root = document.documentElement;
  if (resolved === 'dark') {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }
}

const stored = (typeof localStorage !== 'undefined'
  ? localStorage.getItem('lg-theme')
  : null) as Theme | null;

const initial: Theme = stored && ['light', 'dark', 'system'].includes(stored) ? stored : 'light';
const initialResolved = resolveTheme(initial);

// Apply on load
applyThemeToDOM(initialResolved);

export const useThemeStore = create<ThemeState>((set) => ({
  theme: initial,
  resolved: initialResolved,
  setTheme: (theme) => {
    const resolved = resolveTheme(theme);
    localStorage.setItem('lg-theme', theme);
    applyThemeToDOM(resolved);
    set({ theme, resolved });
  },
}));

// Listen for system theme changes
if (typeof window !== 'undefined') {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const state = useThemeStore.getState();
    if (state.theme === 'system') {
      const resolved = getSystemTheme();
      applyThemeToDOM(resolved);
      useThemeStore.setState({ resolved });
    }
  });
}
