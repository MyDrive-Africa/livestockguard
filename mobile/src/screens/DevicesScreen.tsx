import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl } from 'react-native';
import { api } from '../services/api';
import { useFarm } from '../context/FarmContext';

interface Device {
  id: string;
  serial_number: string;
  device_type: string;
  firmware_version?: string;
  status: string;
  battery_level?: number;
  last_seen?: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: '#22c55e',
  inactive: '#6b7280',
  offline: '#ef4444',
  maintenance: '#f59e0b',
};

export default function DevicesScreen() {
  const { selectedFarm } = useFarm();
  const [devices, setDevices] = useState<Device[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDevices = async () => {
    if (!selectedFarm) return;
    try {
      const resp = await api.get(`/api/v1/devices?farm_id=${selectedFarm.id}`);
      setDevices(resp.data);
    } catch (err) {
      console.warn('Failed to fetch devices:', err);
    }
  };

  useEffect(() => { fetchDevices(); }, [selectedFarm]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchDevices();
    setRefreshing(false);
  };

  const formatLastSeen = (isoString?: string): string => {
    if (!isoString) return 'Never';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    return `${diffDays}d ago`;
  };

  const getBatteryIcon = (level?: number): string => {
    if (level === undefined || level === null) return '🔋';
    if (level > 75) return '🔋';
    if (level > 50) return '🪫';
    if (level > 25) return '🪫';
    return '⚠️';
  };

  const getBatteryColor = (level?: number): string => {
    if (level === undefined || level === null) return '#6b7280';
    if (level > 75) return '#22c55e';
    if (level > 50) return '#84cc16';
    if (level > 25) return '#f59e0b';
    return '#ef4444';
  };

  const getDeviceIcon = (type: string): string => {
    switch (type) {
      case 'collar': return '📡';
      case 'ear_tag': return '🏷️';
      case 'gateway': return '📶';
      default: return '📟';
    }
  };

  const renderDevice = ({ item }: { item: Device }) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.deviceIcon}>{getDeviceIcon(item.device_type)}</Text>
        <View style={styles.cardHeaderText}>
          <Text style={styles.serialNumber}>{item.serial_number}</Text>
          <Text style={styles.deviceType}>{item.device_type.replace(/_/g, ' ')}</Text>
        </View>
        <View style={[styles.statusDot, { backgroundColor: STATUS_COLORS[item.status] || '#6b7280' }]} />
      </View>

      <View style={styles.statsRow}>
        {/* Battery */}
        <View style={styles.stat}>
          <Text style={styles.statIcon}>{getBatteryIcon(item.battery_level)}</Text>
          <Text style={[styles.statValue, { color: getBatteryColor(item.battery_level) }]}>
            {item.battery_level !== undefined && item.battery_level !== null ? `${item.battery_level}%` : '—'}
          </Text>
        </View>

        {/* Last Seen */}
        <View style={styles.stat}>
          <Text style={styles.statIcon}>📍</Text>
          <Text style={styles.statValue}>{formatLastSeen(item.last_seen)}</Text>
        </View>

        {/* Firmware */}
        {item.firmware_version && (
          <View style={styles.stat}>
            <Text style={styles.statIcon}>⚙️</Text>
            <Text style={styles.statValue}>v{item.firmware_version}</Text>
          </View>
        )}
      </View>

      {/* Status Badge */}
      <View style={styles.footer}>
        <View style={[styles.statusBadge, { backgroundColor: `${STATUS_COLORS[item.status] || '#6b7280'}20` }]}>
          <Text style={[styles.statusText, { color: STATUS_COLORS[item.status] || '#6b7280' }]}>
            {item.status}
          </Text>
        </View>
      </View>
    </View>
  );

  const activeCount = devices.filter(d => d.status === 'active').length;
  const lowBatteryCount = devices.filter(d => d.battery_level !== undefined && d.battery_level < 25).length;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Devices ({devices.length})</Text>

      {/* Summary Stats */}
      {devices.length > 0 && (
        <View style={styles.summaryRow}>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryValue}>{activeCount}</Text>
            <Text style={styles.summaryLabel}>Active</Text>
          </View>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryValue}>{devices.length - activeCount}</Text>
            <Text style={styles.summaryLabel}>Offline</Text>
          </View>
          <View style={styles.summaryCard}>
            <Text style={[styles.summaryValue, lowBatteryCount > 0 && { color: '#ef4444' }]}>
              {lowBatteryCount}
            </Text>
            <Text style={styles.summaryLabel}>Low Battery</Text>
          </View>
        </View>
      )}

      <FlatList
        data={devices}
        keyExtractor={(item) => item.id}
        renderItem={renderDevice}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" />}
        contentContainerStyle={{ paddingBottom: 40 }}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>📡</Text>
            <Text style={styles.emptyText}>No devices registered</Text>
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
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  deviceIcon: { fontSize: 22, marginRight: 10 },
  cardHeaderText: { flex: 1 },
  serialNumber: { fontSize: 14, fontWeight: '600', color: '#fff' },
  deviceType: { fontSize: 12, color: '#6b7280', marginTop: 1, textTransform: 'capitalize' },
  statusDot: { width: 10, height: 10, borderRadius: 5 },
  statsRow: { flexDirection: 'row', gap: 16 },
  stat: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  statIcon: { fontSize: 14 },
  statValue: { fontSize: 12, color: '#9ca3af' },
  footer: { marginTop: 10 },
  statusBadge: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 3, borderRadius: 10 },
  statusText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  empty: { alignItems: 'center', paddingTop: 60 },
  emptyIcon: { fontSize: 40, marginBottom: 12 },
  emptyText: { fontSize: 14, color: '#6b7280' },
});
