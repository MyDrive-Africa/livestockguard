import { useThemeStore, type Theme } from '@/stores/themeStore';
import clsx from 'clsx';

const options: { value: Theme; label: string; icon: string }[] = [
  { value: 'light', label: 'Light', icon: '☀️' },
  { value: 'dark', label: 'Dark', icon: '🌙' },
  { value: 'system', label: 'Auto', icon: '💻' },
];

export default function ThemeToggle() {
  const { theme, setTheme } = useThemeStore();

  return (
    <div className="flex items-center gap-1 bg-gray-200 dark:bg-gray-700 rounded-lg p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => setTheme(opt.value)}
          title={opt.label}
          className={clsx(
            'px-2 py-1 rounded-md text-xs transition-all duration-200',
            theme === opt.value
              ? 'bg-white dark:bg-gray-600 shadow-sm text-gray-900 dark:text-white'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
          )}
        >
          {opt.icon}
        </button>
      ))}
    </div>
  );
}
