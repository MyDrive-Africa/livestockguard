import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl, TouchableOpacity, ActivityIndicator } from 'react-native';
import { api } from '../services/api';
import { useFarm } from '../context/FarmContext';

interface Alert {
  id: string;
  animal_id?: string;
  animal_name?: string;
  alert_type: string;
  severity: string;
  status: string;
  message: string;
  created_at: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high: '#ef4444',
  medium: '#f59e0b',
  low: '#3b82f6',
  info: '#6b7280',
};

const SEVERITY_ICONS: Record<string, string> = {
  critical: '🚨',
  high: '⚠️',
  medium: '🔶',
  low: 'ℹ️',
  info: '💬',
};

export default function AlertsScreen() {
  const { selectedFarm } = useFarm();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<'active' | 'all'>('active');

  const fetchAlerts = async () => {
    if (!selectedFarm) return;
    try {
      const params = filter === 'active' ? '&status=active' : '';
      const resp = await api.get(`/api/v1/alerts?farm_id=${selectedFarm.id}${params}`);
      setAlerts(resp.data);
    } catch (err) {
      console.warn('Failed to fetch alerts:', err);
    }
  };

  useEffect(() => { fetchAlerts(); }, [selectedFarm, filter]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchAlerts();
    setRefreshing(false);
  };

  const acknowledgeAlert = async (alertId: string) => {
    try {
      await api.put(`/api/v1/alerts/${alertId}/acknowledge`);
      await fetchAlerts();
    } catch (err) {
      console.warn('Failed to acknowledge alert:', err);
    }
  };

  const resolveAlert = async (alertId: string) => {
    try {
      await api.put(`/api/v1/alerts/${alertId}/resolve`);
      await fetchAlerts();
    } catch (err) {
      console.warn('Failed to resolve alert:', err);
    }
  };

  const formatTime = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    return `${diffDays}d ago`;
  };

  const renderAlert = ({ item }: { item: Alert }) => (
    <View style={[styles.card, { borderLeftColor: SEVERITY_COLORS[item.severity] || '#6b7280' }]}>
      <View style={styles.cardHeader}>
        <Text style={styles.severityIcon}>{SEVERITY_ICONS[item.severity] || '⚠️'}</Text>
        <View style={styles.cardHeaderText}>
          <Text style={styles.alertType}>{item.alert_type.replace(/_/g, ' ')}</Text>
          <Text style={styles.timestamp}>{formatTime(item.created_at)}</Text>
        </View>
        <View style={[styles.severityBadge, { backgroundColor: SEVERITY_COLORS[item.severity] || '#6b7280' }]}>
          <Text style={styles.severityText}>{item.severity}</Text>
        </View>
      </View>

      <Text style={styles.message}>{item.message}</Text>

      {item.animal_name && (
        <Text style={styles.animalName}>🐄 {item.animal_name}</Text>
      )}

      {item.status === 'active' && (
        <View style={styles.actions}>
          <TouchableOpacity style={styles.btnAcknowledge} onPress={() => acknowledgeAlert(item.id)}>
            <Text style={styles.btnText}>Acknowledge</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.btnResolve} onPress={() => resolveAlert(item.id)}>
            <Text style={styles.btnText}>Resolve</Text>
          </TouchableOpacity>
        </View>
      )}

      {item.status !== 'active' && (
        <View style={styles.statusRow}>
          <Text style={styles.statusLabel}>Status: </Text>
          <Text style={[styles.statusValue, item.status === 'resolved' && { color: '#22c55e' }]}>
            {item.status}
          </Text>
        </View>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Alerts ({alerts.length})</Text>

      {/* Filter Tabs */}
      <View style={styles.filterRow}>
        <TouchableOpacity
          style={[styles.filterBtn, filter === 'active' && styles.filterBtnActive]}
          onPress={() => setFilter('active')}
        >
          <Text style={[styles.filterText, filter === 'active' && styles.filterTextActive]}>Active</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterBtn, filter === 'all' && styles.filterBtnActive]}
          onPress={() => setFilter('all')}
        >
          <Text style={[styles.filterText, filter === 'all' && styles.filterTextActive]}>All</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={alerts}
        keyExtractor={(item) => item.id}
        renderItem={renderAlert}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" />}
        contentContainerStyle={{ paddingBottom: 40 }}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>✅</Text>
            <Text style={styles.emptyText}>No {filter} alerts</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827', padding: 16, paddingTop: 60 },
  title: { fontSize: 20, fontWeight: 'bold', color: '#fff', marginBottom: 12 },
  filterRow: { flexDirection: 'row', marginBottom: 12, gap: 8 },
  filterBtn: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#374151' },
  filterBtnActive: { backgroundColor: '#22c55e' },
  filterText: { fontSize: 13, color: '#9ca3af', fontWeight: '500' },
  filterTextActive: { color: '#fff' },
  card: { backgroundColor: '#1f2937', borderRadius: 10, padding: 14, marginBottom: 10, borderLeftWidth: 4 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  severityIcon: { fontSize: 18, marginRight: 8 },
  cardHeaderText: { flex: 1 },
  alertType: { fontSize: 14, fontWeight: '600', color: '#fff', textTransform: 'capitalize' },
  timestamp: { fontSize: 11, color: '#6b7280', marginTop: 1 },
  severityBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  severityText: { fontSize: 10, color: '#fff', fontWeight: '700', textTransform: 'uppercase' },
  message: { fontSize: 13, color: '#d1d5db', lineHeight: 18 },
  animalName: { fontSize: 12, color: '#9ca3af', marginTop: 6 },
  actions: { flexDirection: 'row', marginTop: 10, gap: 8 },
  btnAcknowledge: { flex: 1, backgroundColor: '#374151', borderRadius: 8, paddingVertical: 8, alignItems: 'center' },
  btnResolve: { flex: 1, backgroundColor: '#166534', borderRadius: 8, paddingVertical: 8, alignItems: 'center' },
  btnText: { fontSize: 12, fontWeight: '600', color: '#fff' },
  statusRow: { flexDirection: 'row', marginTop: 8 },
  statusLabel: { fontSize: 11, color: '#6b7280' },
  statusValue: { fontSize: 11, color: '#9ca3af', fontWeight: '600', textTransform: 'capitalize' },
  empty: { alignItems: 'center', paddingTop: 60 },
  emptyIcon: { fontSize: 40, marginBottom: 12 },
  emptyText: { fontSize: 14, color: '#6b7280' },
});
