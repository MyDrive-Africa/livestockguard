import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, RefreshControl } from 'react-native';
import { api } from '../services/api';
import { useFarm } from '../context/FarmContext';

interface FarmStats {
  animals: number;
  devices: number;
  geofences: number;
  gateways: number;
  ble_tags: number;
  active_alerts: number;
}

export default function AdminDashboard() {
  const { selectedFarm } = useFarm();
  const [stats, setStats] = useState<FarmStats | null>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    if (!selectedFarm) return;
    try {
      const [systemResp, alertsResp] = await Promise.all([
        api.get(`/api/system/status?farm_id=${selectedFarm.id}`),
        api.get(`/api/alerts?status=active&farm_id=${selectedFarm.id}`),
      ]);
      setStats(systemResp.data.counts);
      setAlerts(alertsResp.data.slice(0, 10));
    } catch (err) {
      console.warn('Failed to fetch admin data:', err);
    }
  };

  useEffect(() => { fetchData(); }, [selectedFarm]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" />}
    >
      <Text style={styles.title}>LivestockGuard</Text>
      <Text style={styles.subtitle}>Farm Dashboard</Text>

      {/* Stats Grid */}
      {stats && (
        <View style={styles.grid}>
          <StatCard label="Animals" value={stats.animals} color="#22c55e" />
          <StatCard label="Devices" value={stats.devices} color="#3b82f6" />
          <StatCard label="Geofences" value={stats.geofences} color="#8b5cf6" />
          <StatCard label="Gateways" value={stats.gateways} color="#f59e0b" />
          <StatCard label="BLE Tags" value={stats.ble_tags} color="#06b6d4" />
          <StatCard label="Active Alerts" value={stats.active_alerts} color={stats.active_alerts > 0 ? '#ef4444' : '#22c55e'} />
        </View>
      )}

      {/* Active Alerts */}
      <Text style={styles.sectionTitle}>
        Active Alerts {alerts.length > 0 && `(${alerts.length})`}
      </Text>
      {alerts.length === 0 ? (
        <View style={styles.noAlerts}>
          <Text style={styles.noAlertsText}>✓ No active alerts</Text>
        </View>
      ) : (
        alerts.map((alert, i) => (
          <View key={alert.id || i} style={styles.alertCard}>
            <View style={styles.alertHeader}>
              <Text style={styles.alertType}>
                {alert.severity === 'critical' ? '🚨' : '⚠️'} {(alert.alert_type || '').replace(/_/g, ' ')}
              </Text>
              <Text style={[styles.alertSeverity, { color: alert.severity === 'critical' ? '#ef4444' : '#f59e0b' }]}>
                {alert.severity}
              </Text>
            </View>
            <Text style={styles.alertMessage}>{alert.message}</Text>
            {alert.animal_name && <Text style={styles.alertAnimal}>🐄 {alert.animal_name}</Text>}
          </View>
        ))
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={styles.statCard}>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827', padding: 16, paddingTop: 60 },
  title: { fontSize: 24, fontWeight: 'bold', color: '#22c55e', textAlign: 'center' },
  subtitle: { fontSize: 14, color: '#9ca3af', textAlign: 'center', marginBottom: 24 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', marginBottom: 24 },
  statCard: { width: '48%', backgroundColor: '#1f2937', borderRadius: 12, padding: 16, alignItems: 'center', marginBottom: 12 },
  statValue: { fontSize: 28, fontWeight: 'bold' },
  statLabel: { fontSize: 12, color: '#9ca3af', marginTop: 4 },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#fff', marginBottom: 12 },
  noAlerts: { backgroundColor: '#14532d', borderRadius: 12, padding: 16, alignItems: 'center' },
  noAlertsText: { color: '#86efac', fontSize: 14, fontWeight: '600' },
  alertCard: { backgroundColor: '#1f2937', borderRadius: 12, padding: 14, marginBottom: 8, borderLeftWidth: 3, borderLeftColor: '#ef4444' },
  alertHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  alertType: { color: '#fff', fontSize: 13, fontWeight: '600', textTransform: 'capitalize' },
  alertSeverity: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  alertMessage: { color: '#d1d5db', fontSize: 12 },
  alertAnimal: { color: '#9ca3af', fontSize: 11, marginTop: 4 },
});
