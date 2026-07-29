import React, { useEffect, useState } from 'react';
import { StatusBar } from 'react-native';
import LoginScreen from './src/screens/LoginScreen';
import HerdsmanScreen from './src/screens/HerdsmanScreen';
import { getToken, getUserRole } from './src/services/api';

/**
 * LivestockGuard Mobile App
 *
 * Dual-role:
 * - Herdsman: Background BLE scanning + simple cattle count view
 * - Admin/Farmer: Full dashboard (map, animals, alerts) — TODO
 */
export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [role, setRole] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if already logged in
    async function checkAuth() {
      const token = await getToken();
      const savedRole = await getUserRole();
      if (token) {
        setAuthenticated(true);
        setRole(savedRole || 'viewer');
      }
      setLoading(false);
    }
    checkAuth();
  }, []);

  if (loading) return null;

  if (!authenticated) {
    return (
      <>
        <StatusBar barStyle="dark-content" />
        <LoginScreen onLogin={(r) => { setAuthenticated(true); setRole(r); }} />
      </>
    );
  }

  // Role-based view
  if (role === 'herdsman') {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <HerdsmanScreen />
      </>
    );
  }

  // Admin/Farmer/Viewer — full dashboard (TODO: add navigation + screens)
  return (
    <>
      <StatusBar barStyle="light-content" />
      <HerdsmanScreen />
    </>
  );
}
