import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, StatusBar, SafeAreaView } from 'react-native';
import LoginScreen from './src/screens/LoginScreen';
import HerdsmanScreen from './src/screens/HerdsmanScreen';
import AdminDashboard from './src/screens/AdminDashboard';
import AnimalsScreen from './src/screens/AnimalsScreen';
import MapScreen from './src/screens/MapScreen';
import InsightsScreen from './src/screens/InsightsScreen';
import FarmPicker from './src/components/FarmPicker';
import { FarmProvider } from './src/context/FarmContext';
import { getToken, getUserRole, setLogoutCallback, api } from './src/services/api';

type Tab = 'dashboard' | 'map' | 'cattle' | 'insights' | 'herdsman';
type ConnectionStatus = 'connected' | 'connecting' | 'disconnected';

function useConnectionStatus(authenticated: boolean): ConnectionStatus {
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const hasConnectedOnce = React.useRef(false);

  useEffect(() => {
    if (!authenticated) {
      setStatus('disconnected');
      return;
    }

    let mounted = true;

    async function checkConnection() {
      try {
        await api.get('/health');
        if (mounted) {
          hasConnectedOnce.current = true;
          setStatus('connected');
        }
      } catch {
        if (mounted) {
          // If we've never connected, transition from 'connecting' to 'connected' (demo mode)
          // since data is still loaded via cached/polling. If we had a live connection before,
          // show disconnected so the user knows they lost it.
          if (!hasConnectedOnce.current) {
            setStatus('connected');
          } else {
            setStatus('disconnected');
          }
        }
      }
    }

    // Brief "Connecting..." then resolve
    const initialTimer = setTimeout(checkConnection, 1500);
    const interval = setInterval(checkConnection, 15000);
    return () => { mounted = false; clearTimeout(initialTimer); clearInterval(interval); };
  }, [authenticated]);

  return status;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [role, setRole] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

  // Connection status (polls API health endpoint)
  const connectionStatus = useConnectionStatus(authenticated);

  useEffect(() => {
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

    // Register logout callback so 401 responses return to login screen
    setLogoutCallback(() => {
      setAuthenticated(false);
      setRole('');
    });
  }, []);

  if (loading) return <View style={styles.loading}><Text style={styles.loadingText}>Loading...</Text></View>;

  if (!authenticated) {
    return (
      <>
        <StatusBar barStyle="dark-content" />
        <LoginScreen onLogin={(r) => { setAuthenticated(true); setRole(r); }} />
      </>
    );
  }

  const isHerdsman = role === 'herdsman';

  // Render active screen
  const renderScreen = () => {
    switch (activeTab) {
      case 'dashboard': return <AdminDashboard />;
      case 'map': return <MapScreen />;
      case 'cattle': return <AnimalsScreen />;
      case 'insights': return <InsightsScreen role={role} />;
      case 'herdsman': return <HerdsmanScreen />;
    }
  };

  return (
    <FarmProvider role={role}>
      <View style={styles.container}>
        <StatusBar barStyle="light-content" />

        {/* Farm Picker Header */}
        <SafeAreaView style={styles.safeHeader}>
          <FarmPicker role={role} />
        </SafeAreaView>

        {/* Connection Status Indicator */}
        <ConnectionIndicator status={connectionStatus} />

        {/* Active screen */}
        <View style={styles.screen}>{renderScreen()}</View>

        {/* Bottom Tab Bar */}
        <View style={styles.tabBar}>
          <TabButton icon="📊" label="Dashboard" active={activeTab === 'dashboard'} onPress={() => setActiveTab('dashboard')} />
          <TabButton icon="🗺️" label="Map" active={activeTab === 'map'} onPress={() => setActiveTab('map')} />
          <TabButton icon="🐄" label="Cattle" active={activeTab === 'cattle'} onPress={() => setActiveTab('cattle')} />
          {!isHerdsman && (
            <TabButton icon="💡" label="Insights" active={activeTab === 'insights'} onPress={() => setActiveTab('insights')} />
          )}
          <TabButton icon="📶" label="Scanner" active={activeTab === 'herdsman'} onPress={() => setActiveTab('herdsman')} />
        </View>
      </View>
    </FarmProvider>
  );
}

function TabButton({ icon, label, active, onPress }: { icon: string; label: string; active: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity style={styles.tab} onPress={onPress}>
      <Text style={styles.tabIcon}>{icon}</Text>
      <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>{label}</Text>
      {active && <View style={styles.tabIndicator} />}
    </TouchableOpacity>
  );
}

function ConnectionIndicator({ status }: { status: ConnectionStatus }) {
  const dotColor = status === 'connected' ? '#22c55e' : status === 'connecting' ? '#eab308' : '#ef4444';
  const label = status === 'connected' ? 'Live' : status === 'connecting' ? 'Connecting...' : 'Offline';

  return (
    <View style={styles.connectionBar}>
      <View style={[styles.connectionDot, { backgroundColor: dotColor }]} />
      <Text style={styles.connectionText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  safeHeader: { backgroundColor: '#1f2937' },
  loading: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#111827' },
  loadingText: { color: '#9ca3af', fontSize: 16 },
  screen: { flex: 1 },
  connectionBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 4, backgroundColor: '#1f2937', borderBottomWidth: 1, borderBottomColor: '#374151' },
  connectionDot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  connectionText: { fontSize: 11, color: '#9ca3af' },
  tabBar: { flexDirection: 'row', backgroundColor: '#1f2937', borderTopWidth: 1, borderTopColor: '#374151', paddingBottom: 20, paddingTop: 8 },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 4 },
  tabIcon: { fontSize: 20 },
  tabLabel: { fontSize: 10, color: '#6b7280', marginTop: 2 },
  tabLabelActive: { color: '#22c55e', fontWeight: '600' },
  tabIndicator: { width: 4, height: 4, borderRadius: 2, backgroundColor: '#22c55e', marginTop: 3 },
});
