import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Platform, TouchableOpacity } from 'react-native';
import MapView, { Marker, Polygon, Polyline, Callout } from 'react-native-maps';
import { api } from '../services/api';

interface AnimalPosition {
  id: string;
  name: string;
  tag_id: string;
  breed?: string;
  gender?: string;
  last_latitude?: number;
  last_longitude?: number;
  last_speed?: number;
}

interface Geofence {
  id: string;
  name: string;
  fence_type: string;
  area_hectares?: number;
  geometry?: { type: string; coordinates: number[][][] };
}

type MapType = 'standard' | 'satellite' | 'hybrid';

const INITIAL_REGION = {
  latitude: -26.719088,
  longitude: 27.709759,
  latitudeDelta: 0.006,
  longitudeDelta: 0.006,
};

export default function MapScreen() {
  const [animals, setAnimals] = useState<AnimalPosition[]>([]);
  const [geofences, setGeofences] = useState<Geofence[]>([]);
  const [mapType, setMapType] = useState<MapType>('standard');
  const [trail, setTrail] = useState<{ lat: number; lon: number }[]>([]);
  const [selectedAnimal, setSelectedAnimal] = useState<string | null>(null);

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

  const fetchTrail = async (animalId: string) => {
    try {
      const resp = await api.get(`/api/animals/${animalId}/history?hours=24`);
      setTrail(resp.data.positions || []);
      setSelectedAnimal(animalId);
    } catch {
      setTrail([]);
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

  const withPosition = animals.filter(a => a.last_latitude != null);

  return (
    <View style={styles.container}>
      <MapView
        style={styles.map}
        initialRegion={INITIAL_REGION}
        mapType={mapType}
        showsUserLocation={false}
        showsCompass={true}
        showsScale={true}
      >
        {/* Geofence polygons with labels */}
        {geofences.map((fence) => {
          if (!fence.geometry?.coordinates?.[0]) return null;
          const coords = fence.geometry.coordinates[0].map(([lon, lat]) => ({
            latitude: lat,
            longitude: lon,
          }));
          // Calculate centroid for label
          const cx = coords.reduce((s, c) => s + c.latitude, 0) / coords.length;
          const cy = coords.reduce((s, c) => s + c.longitude, 0) / coords.length;
          const isExclusion = fence.fence_type === 'exclusion';
          const areaText = fence.area_hectares
            ? fence.area_hectares >= 100 ? `${(fence.area_hectares/100).toFixed(0)} km²`
              : fence.area_hectares >= 1 ? `${fence.area_hectares.toFixed(1)} ha`
              : `${Math.round(fence.area_hectares * 10000)} m²`
            : '';

          return (
            <React.Fragment key={fence.id}>
              <Polygon
                coordinates={coords}
                strokeColor={isExclusion ? '#ef4444' : '#22c55e'}
                fillColor={isExclusion ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)'}
                strokeWidth={2}
              />
              {/* Geofence label marker */}
              <Marker
                coordinate={{ latitude: cx, longitude: cy }}
                anchor={{ x: 0.5, y: 0.5 }}
                tracksViewChanges={false}
              >
                <View style={[styles.fenceLabel, { backgroundColor: isExclusion ? '#ef4444' : '#16a34a' }]}>
                  <Text style={styles.fenceLabelText}>{fence.name}{areaText ? ` · ${areaText}` : ''}</Text>
                </View>
              </Marker>
            </React.Fragment>
          );
        })}

        {/* Trail polyline */}
        {trail.length > 1 && (
          <Polyline
            coordinates={trail.map(p => ({ latitude: p.lat, longitude: p.lon }))}
            strokeColor="#8b5cf6"
            strokeWidth={3}
          />
        )}

        {/* Cattle markers with cow emoji */}
        {withPosition.map((animal) => (
          <Marker
            key={animal.id}
            coordinate={{
              latitude: animal.last_latitude!,
              longitude: animal.last_longitude!,
            }}
            onPress={() => fetchTrail(animal.id)}
            tracksViewChanges={false}
          >
            <View style={styles.cowMarker}>
              <Text style={styles.cowEmoji}>🐄</Text>
            </View>
            <Callout>
              <View style={styles.callout}>
                <Text style={styles.calloutTitle}>{animal.name}</Text>
                <Text style={styles.calloutDetail}>
                  {animal.breed || ''} {animal.gender === 'male' ? '♂' : animal.gender === 'female' ? '♀' : ''}
                </Text>
                {animal.last_speed != null && <Text style={styles.calloutDetail}>Speed: {animal.last_speed.toFixed(1)} km/h</Text>}
                <Text style={styles.calloutHint}>Tap for trail</Text>
              </View>
            </Callout>
          </Marker>
        ))}
      </MapView>

      {/* Map type switcher */}
      <View style={styles.mapTypeSwitcher}>
        {(['standard', 'satellite', 'hybrid'] as MapType[]).map((type) => (
          <TouchableOpacity
            key={type}
            style={[styles.mapTypeBtn, mapType === type && styles.mapTypeBtnActive]}
            onPress={() => setMapType(type)}
          >
            <Text style={[styles.mapTypeBtnText, mapType === type && styles.mapTypeBtnTextActive]}>
              {type === 'standard' ? '🗺️' : type === 'satellite' ? '🛰️' : '🌍'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Trail info */}
      {selectedAnimal && trail.length > 0 && (
        <TouchableOpacity style={styles.trailInfo} onPress={() => { setTrail([]); setSelectedAnimal(null); }}>
          <Text style={styles.trailInfoText}>📍 Trail: {trail.length} pts · Tap to clear</Text>
        </TouchableOpacity>
      )}

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
  cowMarker: { alignItems: 'center', justifyContent: 'center' },
  cowEmoji: { fontSize: 24 },
  fenceLabel: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  fenceLabelText: { color: '#fff', fontSize: 9, fontWeight: 'bold' },
  callout: { padding: 4, minWidth: 120 },
  calloutTitle: { fontWeight: 'bold', fontSize: 13 },
  calloutDetail: { fontSize: 11, color: '#666' },
  calloutHint: { fontSize: 10, color: '#8b5cf6', marginTop: 2 },
  mapTypeSwitcher: {
    position: 'absolute', top: 60, right: 12,
    backgroundColor: 'rgba(0,0,0,0.7)', borderRadius: 8,
    flexDirection: 'column', padding: 4, gap: 4,
  },
  mapTypeBtn: { padding: 6, borderRadius: 6 },
  mapTypeBtnActive: { backgroundColor: '#22c55e' },
  mapTypeBtnText: { fontSize: 18 },
  mapTypeBtnTextActive: {},
  trailInfo: {
    position: 'absolute', top: 60, left: 12,
    backgroundColor: '#7c3aed', borderRadius: 8, padding: 8,
  },
  trailInfoText: { color: '#fff', fontSize: 11, fontWeight: '600' },
  overlay: {
    position: 'absolute', bottom: 80, left: 16, right: 16,
    backgroundColor: 'rgba(0,0,0,0.7)', borderRadius: 8, padding: 8, alignItems: 'center',
  },
  overlayText: { color: '#fff', fontSize: 12 },
});
