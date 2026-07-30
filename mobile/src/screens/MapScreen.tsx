import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, Platform } from 'react-native';
import { api } from '../services/api';

/**
 * Map Screen — shows cattle positions.
 * On web: embeds the full dashboard map via iframe.
 * On native (Android/iOS): shows position list with live updates.
 * (Future: use react-native-maps for native map with markers)
 */

interface AnimalPosition {
  id: string;
  name: string;
  tag_id: string;
  breed?: string;
  gender?: string;
  last_latitude?: number;
  last_longitude?: number;
  last_speed?: number;
  battery_level?: number;
}

export default function MapScreen() {
  const [animals, setAnimals] = useState<AnimalPosition[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchPositions = async () => {
    try {
      const resp = await api.get('/api/animals');
      setAnimals(resp.data);
    } catch (err) {
      console.warn('Failed to fetch positions:', err);
    }
  };

  useEffect(() => { fetchPositions(); }, []);
  useEffect(() => {
    const interval = setInterval(fetchPositions, 30000);
    return () => clearInterval(interval);
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchPositions();
    setRefreshing(false);
  };

  // Web: embed dashboard map
  if (Platform.OS === 'web') {
    return (
      <View style={styles.container}>
        {/* @ts-ignore - iframe works on web */}
        <iframe
          src="http://localhost:5173"
          style={{ width: '100%', height: '100%', border: 'none' }}
          title="LivestockGuard Map"
        />
      </View>
    );
  }

  // Native: position list (until react-native-maps is added)
  const withPosition = animals.filter(a => a.last_latitude != null);
  const withoutPosition = animals.filter(a => a.last_latitude == null);

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" />}
    >
      <Text style={styles.title}>🗺️ Live Positions</Text>
      <Text style={styles.subtitle}>{withPosition.length} tracked · {withoutPosition.length} no signal · Updates every 30s</Text>

      {withPosition.map((animal) => (
        <View key={animal.id} style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.animalName}>🐄 {animal.name}</Text>
            <View style={styles.liveBadge}>
              <View style={styles.liveDot} />
              <Text style={styles.liveText}>Live</Text>
            </View>
          </View>
          <Text style={styles.coords}>
            📍 {animal.last_latitude?.toFixed(5)}, {animal.last_longitude?.toFixed(5)}
          </Text>
          <View style={styles.detailRow}>
            {animal.last_speed != null && (
              <Text style={styles.detail}>🚶 {animal.last_speed.toFixed(1)} km/h</Text>
            )}
            {animal.battery_level != null && (
              <Text style={[styles.detail, animal.battery_level < 20 && styles.lowBattery]}>
                🔋 {animal.battery_level}%
              </Text>
            )}
            <Text style={styles.detail}>
              {animal.breed || ''} {animal.gender === 'male' ? '♂' : animal.gender === 'female' ? '♀' : ''}
            </Text>
          </View>
        </View>
      ))}

      {withoutPosition.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>No Signal ({withoutPosition.length})</Text>
          {withoutPosition.map((animal) => (
            <View key={animal.id} style={[styles.card, styles.cardOffline]}>
              <Text style={styles.offlineName}>🐄 {animal.name}</Text>
              <Text style={styles.offlineDetail}>{animal.tag_id} · {animal.breed || '—'}</Text>
            </View>
          ))}
        </>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827', padding: 16, paddingTop: 60 },
  title: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  subtitle: { fontSize: 12, color: '#6b7280', marginBottom: 16 },
  card: { backgroundColor: '#1f2937', borderRadius: 12, padding: 14, marginBottom: 10, borderLeftWidth: 3, borderLeftColor: '#22c55e' },
  cardOffline: { borderLeftColor: '#6b7280', opacity: 0.7 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  animalName: { fontSize: 15, fontWeight: '600', color: '#fff' },
  liveBadge: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#14532d', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#22c55e', marginRight: 4 },
  liveText: { fontSize: 10, color: '#86efac', fontWeight: '600' },
  coords: { fontSize: 11, color: '#9ca3af', marginTop: 6 },
  detailRow: { flexDirection: 'row', gap: 12, marginTop: 6 },
  detail: { fontSize: 11, color: '#6b7280' },
  lowBattery: { color: '#ef4444' },
  sectionTitle: { fontSize: 14, fontWeight: '600', color: '#9ca3af', marginTop: 16, marginBottom: 8 },
  offlineName: { fontSize: 14, color: '#9ca3af' },
  offlineDetail: { fontSize: 11, color: '#4b5563', marginTop: 2 },
});
