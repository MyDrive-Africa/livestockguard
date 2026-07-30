import { useState } from 'react';
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const alerts = useRealtimeStore((state) => state.alerts);
  const wsConnected = useRealtimeStore((state) => state.wsConnected);
  const logout = useAuthStore((state) => state.logout);
  const activeAlerts = alerts.filter((a) => a.status === 'active').length;

  // Establish WebSocket connection for real-time updates
  useWebSocket();

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900 theme-transition">
      {/* Sidebar */}
      <aside
        className={`sidebar-collapse bg-brand-900 dark:bg-gray-800 text-white flex flex-col theme-transition ${
          sidebarCollapsed ? 'sidebar-collapsed' : 'sidebar-expanded'
        }`}
      >
        <div className="p-4 border-b border-brand-800 dark:border-gray-700 flex items-center justify-between gap-2">
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <h1 className="text-xl font-bold truncate">LivestockGuard</h1>
              <p className="text-sm text-brand-300 dark:text-gray-400 truncate">Monitoring Dashboard</p>
            </div>
          )}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-1.5 rounded-lg text-brand-200 dark:text-gray-300 hover:bg-brand-800 dark:hover:bg-gray-700 hover:text-white transition-colors flex-shrink-0"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className={`w-5 h-5 transition-transform duration-300 ${sidebarCollapsed ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        </div>

        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              title={sidebarCollapsed ? item.label : undefined}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  sidebarCollapsed ? 'justify-center' : ''
                } ${
                  isActive
                    ? 'bg-brand-700 dark:bg-gray-700 text-white'
                    : 'text-brand-200 dark:text-gray-300 hover:bg-brand-800 dark:hover:bg-gray-700 hover:text-white'
                }`
              }
            >
              <span className="text-lg flex-shrink-0">{item.icon}</span>
              {!sidebarCollapsed && <span>{item.label}</span>}
              {!sidebarCollapsed && item.path === '/alerts' && activeAlerts > 0 && (
                <span className="ml-auto bg-red-500 text-white text-xs px-2 py-0.5 rounded-full animate-pulse-badge">
                  {activeAlerts}
                </span>
              )}
              {sidebarCollapsed && item.path === '/alerts' && activeAlerts > 0 && (
                <span className="absolute top-0 right-0 w-2 h-2 bg-red-500 rounded-full"></span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className={`p-4 border-t border-brand-800 dark:border-gray-700 space-y-3 ${sidebarCollapsed ? 'flex flex-col items-center' : ''}`}>
          {/* Theme Toggle */}
          {!sidebarCollapsed && <ThemeToggle />}

          <div className={`flex items-center gap-2 text-xs text-brand-300 dark:text-gray-400 ${sidebarCollapsed ? 'justify-center' : ''}`}>
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${wsConnected ? 'bg-green-400' : 'bg-red-400'}`}></span>
            {!sidebarCollapsed && (wsConnected ? 'Live' : 'Connecting...')}
          </div>
          {!sidebarCollapsed && (
            <button
              onClick={logout}
              className="w-full px-3 py-2 text-sm text-brand-200 dark:text-gray-300 hover:text-white hover:bg-brand-800 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              Sign Out
            </button>
          )}
          {sidebarCollapsed && (
            <button
              onClick={logout}
              title="Sign Out"
              aria-label="Sign Out"
              className="p-2 text-brand-200 dark:text-gray-300 hover:text-white hover:bg-brand-800 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          )}
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
