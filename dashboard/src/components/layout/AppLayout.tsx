import { NavLink, Outlet } from 'react-router-dom';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { useAuthStore } from '@/stores/authStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import ThemeToggle from '@/components/ThemeToggle';
import ToastContainer from '@/components/ToastContainer';

const navItems = [
  { path: '/map', label: 'Map', icon: '🗺️' },
  { path: '/animals', label: 'Animals', icon: '🐄' },
  { path: '/geofences', label: 'Geofences', icon: '📍' },
  { path: '/alerts', label: 'Alerts', icon: '🔔' },
  { path: '/analytics', label: 'Analytics', icon: '📊' },
  { path: '/devices', label: 'Devices', icon: '📡' },
  { path: '/gateway', label: 'Herdsman', icon: '📶' },
];

export default function AppLayout() {
  const alerts = useRealtimeStore((state) => state.alerts);
  const wsConnected = useRealtimeStore((state) => state.wsConnected);
  const logout = useAuthStore((state) => state.logout);
  const activeAlerts = alerts.filter((a) => a.status === 'active').length;

  // Establish WebSocket connection for real-time updates
  useWebSocket();

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900 theme-transition">
      {/* Sidebar */}
      <aside className="w-64 bg-brand-900 dark:bg-gray-800 text-white flex flex-col theme-transition">
        <div className="p-4 border-b border-brand-800 dark:border-gray-700">
          <h1 className="text-xl font-bold">LivestockGuard</h1>
          <p className="text-sm text-brand-300 dark:text-gray-400">Monitoring Dashboard</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-brand-700 dark:bg-gray-700 text-white'
                    : 'text-brand-200 dark:text-gray-300 hover:bg-brand-800 dark:hover:bg-gray-700 hover:text-white'
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
              {item.path === '/alerts' && activeAlerts > 0 && (
                <span className="ml-auto bg-red-500 text-white text-xs px-2 py-0.5 rounded-full animate-pulse-badge">
                  {activeAlerts}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-brand-800 dark:border-gray-700 space-y-3">
          {/* Theme Toggle */}
          <ThemeToggle />

          <div className="flex items-center gap-2 text-xs text-brand-300 dark:text-gray-400">
            <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-red-400'}`}></span>
            {wsConnected ? 'Live' : 'Connecting...'}
          </div>
          <button
            onClick={logout}
            className="w-full px-3 py-2 text-sm text-brand-200 dark:text-gray-300 hover:text-white hover:bg-brand-800 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden relative">
        <div className="absolute inset-0">
          <Outlet />
        </div>
      </main>

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  );
}
