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
