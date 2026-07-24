import { NavLink, Outlet } from 'react-router-dom';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { useAuthStore } from '@/stores/authStore';

const navItems = [
  { path: '/map', label: 'Map', icon: '🗺️' },
  { path: '/animals', label: 'Animals', icon: '🐄' },
  { path: '/geofences', label: 'Geofences', icon: '📍' },
  { path: '/alerts', label: 'Alerts', icon: '🔔' },
  { path: '/analytics', label: 'Analytics', icon: '📊' },
  { path: '/devices', label: 'Devices', icon: '📡' },
];

export default function AppLayout() {
  const alerts = useRealtimeStore((state) => state.alerts);
  const logout = useAuthStore((state) => state.logout);
  const activeAlerts = alerts.filter((a) => a.status === 'active').length;

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-brand-900 text-white flex flex-col">
        <div className="p-4 border-b border-brand-800">
          <h1 className="text-xl font-bold">LivestockGuard</h1>
          <p className="text-sm text-brand-300">Monitoring Dashboard</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-brand-700 text-white'
                    : 'text-brand-200 hover:bg-brand-800 hover:text-white'
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
              {item.path === '/alerts' && activeAlerts > 0 && (
                <span className="ml-auto bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                  {activeAlerts}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-brand-800">
          <button
            onClick={logout}
            className="w-full px-3 py-2 text-sm text-brand-200 hover:text-white hover:bg-brand-800 rounded-lg transition-colors"
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
    </div>
  );
}
