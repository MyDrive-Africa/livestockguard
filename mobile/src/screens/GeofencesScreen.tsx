import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl } from 'react-native';
import { api } from '../services/api';
import { useFarm } from '../context/FarmContext';

interface Geofence {
  id: string;
  name: string;
  fence_type: string;
  active: boolean;
  alert_on_breach: boolean;
  animals_inside?: number;
  animals_outside?: number;
}

export default function GeofencesScreen() {
  const { selectedFarm } = useFarm();
  const [geofences, setGeofences] = useState<Geofence[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchGeofences = async () => {
    if (!selectedFarm) return;
    try {
      const resp = await api.get(`/api/v1/geofences?farm_id=${selectedFarm.id}`);
      setGeofences(resp.data);
    } catch (err) {
      console.warn('Failed to fetch geofences:', err);
    }
  };

  useEffect(() => { fetchGeofences(); }, [selectedFarm]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchGeofences();
    setRefreshing(false);
  };

  const getFenceIcon = (type: string): string => {
    return type === 'inclusion' ? '🟢' : '🔴';
  };

  const renderGeofence = ({ item }: { item: Geofence }) => (
    <View style={[styles.card, !item.active && styles.cardInactive]}>
      <View style={styles.cardHeader}>
        <Text style={styles.fenceIcon}>{getFenceIcon(item.fence_type)}</Text>
        <View style={styles.cardHeaderText}>
          <Text style={styles.name}>{item.name}</Text>
          <Text style={styles.fenceType}>
            {item.fence_type === 'inclusion' ? 'Keep inside' : 'Keep outside'}
          </Text>
        </View>
        <View style={[styles.activeBadge, { backgroundColor: item.active ? '#16532420' : '#37415180' }]}>
          <Text style={[styles.activeText, { color: item.active ? '#22c55e' : '#6b7280' }]}>
            {item.active ? 'Active' : 'Inactive'}
          </Text>
        </View>
      </View>

      {/* Animal Count */}
      <View style={styles.countRow}>
        <View style={styles.countItem}>
          <Text style={styles.countIcon}>🐄</Text>
          <Text style={styles.countLabel}>Inside</Text>
          <Text style={styles.countValue}>{item.animals_inside ?? '—'}</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.countItem}>
          <Text style={styles.countIcon}>🚨</Text>
          <Text style={styles.countLabel}>Outside</Text>
          <Text style={[styles.countValue, (item.animals_outside ?? 0) > 0 && styles.countWarning]}>
            {item.animals_outside ?? '—'}
          </Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.countItem}>
          <Text style={styles.countIcon}>🔔</Text>
          <Text style={styles.countLabel}>Alerts</Text>
          <Text style={styles.countValue}>{item.alert_on_breach ? 'On' : 'Off'}</Text>
        </View>
      </View>
    </View>
  );

  const activeCount = geofences.filter(g => g.active).length;
  const totalOutside = geofences.reduce((sum, g) => sum + (g.animals_outside ?? 0), 0);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Geofences ({geofences.length})</Text>

      {/* Summary */}
      {geofences.length > 0 && (
        <View style={styles.summaryRow}>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryValue}>{activeCount}</Text>
            <Text style={styles.summaryLabel}>Active</Text>
          </View>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryValue}>{geofences.length - activeCount}</Text>
            <Text style={styles.summaryLabel}>Inactive</Text>
          </View>
          <View style={styles.summaryCard}>
            <Text style={[styles.summaryValue, totalOutside > 0 && { color: '#ef4444' }]}>
              {totalOutside}
            </Text>
            <Text style={styles.summaryLabel}>Breaches</Text>
          </View>
        </View>
      )}

      <FlatList
        data={geofences}
        keyExtractor={(item) => item.id}
        renderItem={renderGeofence}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" />}
        contentContainerStyle={{ paddingBottom: 40 }}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>🗺️</Text>
            <Text style={styles.emptyText}>No geofences configured</Text>
            <Text style={styles.emptySubtext}>Create geofences from the web dashboard</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827', padding: 16, paddingTop: 60 },
  title: { fontSize: 20, fontWeight: 'bold', color: '#fff', marginBottom: 12 },
  summaryRow: { flexDirection: 'row', gap: 8, marginBottom: 14 },
  summaryCard: { flex: 1, backgroundColor: '#1f2937', borderRadius: 10, padding: 12, alignItems: 'center' },
  summaryValue: { fontSize: 20, fontWeight: '700', color: '#fff' },
  summaryLabel: { fontSize: 11, color: '#6b7280', marginTop: 2 },
  card: { backgroundColor: '#1f2937', borderRadius: 10, padding: 14, marginBottom: 10 },
  cardInactive: { opacity: 0.6 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  fenceIcon: { fontSize: 20, marginRight: 10 },
  cardHeaderText: { flex: 1 },
  name: { fontSize: 15, fontWeight: '600', color: '#fff' },
  fenceType: { fontSize: 12, color: '#6b7280', marginTop: 1 },
  activeBadge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 10 },
  activeText: { fontSize: 11, fontWeight: '600' },
  countRow: { flexDirection: 'row', backgroundColor: '#111827', borderRadius: 8, padding: 12 },
  countItem: { flex: 1, alignItems: 'center' },
  countIcon: { fontSize: 16, marginBottom: 4 },
  countLabel: { fontSize: 10, color: '#6b7280', marginBottom: 2 },
  countValue: { fontSize: 15, fontWeight: '700', color: '#fff' },
  countWarning: { color: '#ef4444' },
  divider: { width: 1, backgroundColor: '#374151', marginHorizontal: 8 },
  empty: { alignItems: 'center', paddingTop: 60 },
  emptyIcon: { fontSize: 40, marginBottom: 12 },
  emptyText: { fontSize: 14, color: '#6b7280' },
  emptySubtext: { fontSize: 12, color: '#4b5563', marginTop: 4 },
});
