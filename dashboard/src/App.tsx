import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import AppLayout from '@/components/layout/AppLayout';
import LoginPage from '@/pages/auth/LoginPage';
import MapPage from '@/pages/map/MapPage';
import AnimalsPage from '@/pages/animals/AnimalsPage';
import GeofencesPage from '@/pages/geofences/GeofencesPage';
import AlertsPage from '@/pages/alerts/AlertsPage';
import AnalyticsPage from '@/pages/analytics/AnalyticsPage';
import DevicesPage from '@/pages/devices/DevicesPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((state) => state.token);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/map" replace />} />
        <Route path="map" element={<MapPage />} />
        <Route path="animals" element={<AnimalsPage />} />
        <Route path="geofences" element={<GeofencesPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="devices" element={<DevicesPage />} />
      </Route>
    </Routes>
  );
}
