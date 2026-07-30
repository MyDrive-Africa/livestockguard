import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import MapView, { Marker, Polygon, PROVIDER_GOOGLE } from 'react-native-maps';
import { api } from '../services/api';

/**
 * Map Screen — native interactive map with cattle markers and geofences.
 * Uses react-native-maps (Google Maps on Android, Apple Maps on iOS).
 * Web mode falls back to iframe of the web dashboard.
 */

interface AnimalPosition {
  id: string;
  name: string;
  tag_id: string;
  breed?: string;
  gender?: string;
  last_latitude?: number;
  last_longitude?: number;
}

interface Geofence {
  id: string;
  name: string;
  fence_type: string;
  geometry?: { type: string; coordinates: number[][][] };
}

// Loch Vaal Plot 30 centre
const INITIAL_REGION = {
  latitude: -26.719088,
  longitude: 27.709759,
  latitudeDelta: 0.008,
  longitudeDelta: 0.008,
};

export default function MapScreen() {
  const [animals, setAnimals] = useState<AnimalPosition[]>([]);
  const [geofences, setGeofences] = useState<Geofence[]>([]);

  const fetchData = async () => {
    try {
      const [animalsResp, geofencesResp] = await Promise.all([
        api.get('/api/animals'),
        api.get('/api/geofences?farm_id=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'),
      ]);
      setAnimals(animalsResp.data);
      setGeofences(geofencesResp.data);
    } catch (err) {
      console.warn('Failed to fetch map data:', err);
    }
  };

  useEffect(() => { fetchData(); }, []);
  useEffect(() => {
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  // Web: iframe
  if (Platform.OS === 'web') {
    return (
      <View style={styles.container}>
        {/* @ts-ignore */}
        <iframe src="http://localhost:5173" style={{ width: '100%', height: '100%', border: 'none' }} title="Map" />
      </View>
    );
  }

  // Native: react-native-maps
  const withPosition = animals.filter(a => a.last_latitude != null);

  return (
    <View style={styles.container}>
      <MapView
        style={styles.map}
        provider={Platform.OS === 'android' ? PROVIDER_GOOGLE : undefined}
        initialRegion={INITIAL_REGION}
        showsUserLocation={false}
        mapType="hybrid"
      >
        {/* Geofence polygons */}
        {geofences.map((fence) => {
          if (!fence.geometry?.coordinates?.[0]) return null;
          const coords = fence.geometry.coordinates[0].map(([lon, lat]) => ({
            latitude: lat,
            longitude: lon,
          }));
          return (
            <Polygon
              key={fence.id}
              coordinates={coords}
              strokeColor={fence.fence_type === 'exclusion' ? '#ef4444' : '#22c55e'}
              fillColor={fence.fence_type === 'exclusion' ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)'}
              strokeWidth={2}
            />
          );
        })}

        {/* Cattle markers */}
        {withPosition.map((animal) => (
          <Marker
            key={animal.id}
            coordinate={{
              latitude: animal.last_latitude!,
              longitude: animal.last_longitude!,
            }}
            title={animal.name}
            description={`${animal.breed || ''} ${animal.gender === 'male' ? '♂' : animal.gender === 'female' ? '♀' : ''}`}
            pinColor="#16a34a"
          />
        ))}
      </MapView>

      {/* Overlay: count */}
      <View style={styles.overlay}>
        <Text style={styles.overlayText}>🐄 {withPosition.length} tracked · Updates every 30s</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  map: { flex: 1 },
  overlay: {
    position: 'absolute',
    bottom: 80,
    left: 16,
    right: 16,
    backgroundColor: 'rgba(0,0,0,0.7)',
    borderRadius: 8,
    padding: 8,
    alignItems: 'center',
  },
  overlayText: { color: '#fff', fontSize: 12 },
});
