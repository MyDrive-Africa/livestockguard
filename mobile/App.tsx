import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, StatusBar, SafeAreaView } from 'react-native';
import LoginScreen from './src/screens/LoginScreen';
import HerdsmanScreen from './src/screens/HerdsmanScreen';
import AdminDashboard from './src/screens/AdminDashboard';
import AnimalsScreen from './src/screens/AnimalsScreen';
import MapScreen from './src/screens/MapScreen';
import FarmPicker from './src/components/FarmPicker';
import { FarmProvider } from './src/context/FarmContext';
import { getToken, getUserRole, setLogoutCallback } from './src/services/api';

type Tab = 'dashboard' | 'map' | 'cattle' | 'herdsman';

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [role, setRole] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

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

  // Render active screen
  const renderScreen = () => {
    switch (activeTab) {
      case 'dashboard': return <AdminDashboard />;
      case 'map': return <MapScreen />;
      case 'cattle': return <AnimalsScreen />;
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

        {/* Active screen */}
        <View style={styles.screen}>{renderScreen()}</View>

        {/* Bottom Tab Bar */}
        <View style={styles.tabBar}>
          <TabButton icon="📊" label="Dashboard" active={activeTab === 'dashboard'} onPress={() => setActiveTab('dashboard')} />
          <TabButton icon="🗺️" label="Map" active={activeTab === 'map'} onPress={() => setActiveTab('map')} />
          <TabButton icon="🐄" label="Cattle" active={activeTab === 'cattle'} onPress={() => setActiveTab('cattle')} />
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

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  safeHeader: { backgroundColor: '#1f2937' },
  loading: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#111827' },
  loadingText: { color: '#9ca3af', fontSize: 16 },
  screen: { flex: 1 },
  tabBar: { flexDirection: 'row', backgroundColor: '#1f2937', borderTopWidth: 1, borderTopColor: '#374151', paddingBottom: 20, paddingTop: 8 },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 4 },
  tabIcon: { fontSize: 20 },
  tabLabel: { fontSize: 10, color: '#6b7280', marginTop: 2 },
  tabLabelActive: { color: '#22c55e', fontWeight: '600' },
  tabIndicator: { width: 4, height: 4, borderRadius: 2, backgroundColor: '#22c55e', marginTop: 3 },
});
