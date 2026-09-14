import React, { useEffect, useState, useRef } from 'react';
import { View, Text, StyleSheet, Platform, TouchableOpacity, ScrollView, Alert } from 'react-native';
import MapView, { Marker, Polygon, Polyline, Circle, Region } from 'react-native-maps';
import { api, getRobots, getHerdingStatus, sendRobotCommand, stopAllRobots, Robot, HerdingStatus } from '../services/api';
import { useFarm } from '../context/FarmContext';

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
  // Boundary shape (migration 013). For 'circle', centre + radius is authoritative.
  shape?: string;
  center_latitude?: number;
  center_longitude?: number;
  radius_m?: number;
  buffer_m?: number;
}

/** Marker tint by robot status — active states are pink, idle purple, muted greys. */
function robotTint(status?: string): string {
  if (status === 'charging') return '#c4b5fd';
  if (status === 'fault' || status === 'offline') return '#9ca3af';
  if (status === 'shepherding' || status === 'enroute') return '#db2777';
  return '#a855f7';
}

interface GatewayPosition {
  id: string;
  serial_number: string;
  name: string;
  herdsman_name?: string;
  last_latitude?: number;
  last_longitude?: number;
  last_battery_pct?: number;
  last_seen?: string;
}

type MapType = 'standard' | 'satellite' | 'hybrid';

const INITIAL_REGION = {
  latitude: -26.719088,
  longitude: 27.709759,
  latitudeDelta: 0.006,
  longitudeDelta: 0.006,
};

export default function MapScreen() {
  const { selectedFarm } = useFarm();
  const mapRef = useRef<MapView>(null);
  const [animals, setAnimals] = useState<AnimalPosition[]>([]);
  const [geofences, setGeofences] = useState<Geofence[]>([]);
  const [gateways, setGateways] = useState<GatewayPosition[]>([]);
  const [mapType, setMapType] = useState<MapType>('satellite');
  const [trail, setTrail] = useState<{ lat: number; lon: number }[]>([]);
  const [selectedAnimal, setSelectedAnimal] = useState<string | null>(null);
  const [showGeofences, setShowGeofences] = useState(true);
  const [hiddenFences, setHiddenFences] = useState<Set<string>>(new Set());
  const [selectedFence, setSelectedFence] = useState<string | null>(null);
  const [showLayerPanel, setShowLayerPanel] = useState(false);
  const [showActiveOnly, setShowActiveOnly] = useState(true);
  const [herdsmanInfoVisible, setHerdsmanInfoVisible] = useState(false);
  const [focusedHerdsman, setFocusedHerdsman] = useState<GatewayPosition | null>(null);
  // Robotic herdsman
  const [robots, setRobots] = useState<Robot[]>([]);
  const [herding, setHerding] = useState<HerdingStatus | null>(null);
  const [showRobots, setShowRobots] = useState(true);
  const [showHerdingPanel, setShowHerdingPanel] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [selectedRobot, setSelectedRobot] = useState<string | null>(null);  // serial_number
  const [sendHereMode, setSendHereMode] = useState(false);
  const [robotBusy, setRobotBusy] = useState(false);

  const fetchData = async () => {
    if (!selectedFarm) return;
    try {
      const [animalsResp, geofencesResp, gatewaysResp] = await Promise.all([
        api.get(`/api/v1/animals?farm_id=${selectedFarm.id}`),
        api.get(`/api/v1/geofences?farm_id=${selectedFarm.id}${showActiveOnly ? '&active=true' : ''}`),
        api.get(`/api/v1/gateway?farm_id=${selectedFarm.id}`),
      ]);
      setAnimals(animalsResp.data);
      setGeofences(geofencesResp.data);
      setGateways(gatewaysResp.data);
    } catch (err) {
      console.warn('Failed to fetch map data:', err);
    }
    // Robots are optional (not every farm has a fleet) — fetch separately so a
    // failure here never blanks the rest of the map.
    try {
      const [fleet, status] = await Promise.all([
        getRobots(selectedFarm.id),
        getHerdingStatus(selectedFarm.id),
      ]);
      setRobots(fleet);
      setHerding(status);
    } catch (err) {
      console.warn('Failed to fetch herding fleet:', err);
      setRobots([]);
      setHerding(null);
    }
  };

  /** Emergency stop for the whole fleet — confirm first (safety-critical). */
  const handleStopAll = () => {
    if (!selectedFarm) return;
    Alert.alert(
      'Stop all robots?',
      'This halts every herding robot on this farm immediately.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'STOP ALL',
          style: 'destructive',
          onPress: async () => {
            try {
              setStopping(true);
              const res = await stopAllRobots(selectedFarm.id);
              await fetchData();
              Alert.alert('Fleet halted', `Stop sent to ${res.commands_published}/${res.robots} robots.`);
            } catch {
              Alert.alert('Error', 'Could not reach the fleet. Check the connection and try again.');
            } finally {
              setStopping(false);
            }
          },
        },
      ],
    );
  };

  const focusedRobot = robots.find(r => r.serial_number === selectedRobot) ?? null;

  /** Select a robot (tapping its marker) and centre the map on it. */
  const selectRobot = (r: Robot) => {
    setSelectedRobot(prev => (prev === r.serial_number ? null : r.serial_number));
    setSendHereMode(false);
    if (r.last_latitude != null && r.last_longitude != null) {
      mapRef.current?.animateToRegion({
        latitude: r.last_latitude,
        longitude: r.last_longitude,
        latitudeDelta: 0.004,
        longitudeDelta: 0.004,
      }, 600);
    }
  };

  /**
   * Issue a manual override to the selected robot. `move_to` is handled via
   * "send here" mode (tap the map), so this covers return_home / patrol / stop.
   */
  const handleRobotCommand = async (
    command: 'return_home' | 'patrol' | 'stop',
  ) => {
    if (!focusedRobot) return;
    try {
      setRobotBusy(true);
      await sendRobotCommand(focusedRobot.serial_number, command);
      await fetchData();
    } catch {
      Alert.alert('Error', `Could not send "${command}" to ${focusedRobot.name}.`);
    } finally {
      setRobotBusy(false);
    }
  };

  /** Dispatch the selected robot to a tapped map coordinate (move_to). */
  const handleMapPress = async (lat: number, lon: number) => {
    if (!sendHereMode || !focusedRobot) return;
    setSendHereMode(false);
    try {
      setRobotBusy(true);
      await sendRobotCommand(focusedRobot.serial_number, 'move_to', { latitude: lat, longitude: lon });
      await fetchData();
      Alert.alert('On the way', `${focusedRobot.name} dispatched to ${lat.toFixed(5)}, ${lon.toFixed(5)}.`);
    } catch {
      Alert.alert('Error', `Could not dispatch ${focusedRobot.name}.`);
    } finally {
      setRobotBusy(false);
    }
  };

  // Fly to new farm location when farm changes
  useEffect(() => {
    if (!selectedFarm) return;

    // Use farm coordinates if available, otherwise fit to animals
    if (selectedFarm.latitude && selectedFarm.longitude) {
      mapRef.current?.animateToRegion({
        latitude: selectedFarm.latitude,
        longitude: selectedFarm.longitude,
        latitudeDelta: 0.008,
        longitudeDelta: 0.008,
      }, 800);
    }
  }, [selectedFarm]);

  // Fit map to animal positions after data loads (fallback if farm has no coords)
  useEffect(() => {
    if (!selectedFarm?.latitude && animals.length > 0 && mapRef.current) {
      const withPos = animals.filter(a => a.last_latitude != null);
      if (withPos.length > 0) {
        const lats = withPos.map(a => a.last_latitude!);
        const lons = withPos.map(a => a.last_longitude!);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);
        const minLon = Math.min(...lons);
        const maxLon = Math.max(...lons);
        const padding = 0.002;
        mapRef.current.animateToRegion({
          latitude: (minLat + maxLat) / 2,
          longitude: (minLon + maxLon) / 2,
          latitudeDelta: Math.max(maxLat - minLat + padding, 0.004),
          longitudeDelta: Math.max(maxLon - minLon + padding, 0.004),
        }, 800);
      }
    }
  }, [animals]);

  const fetchTrail = async (animalId: string) => {
    try {
      const resp = await api.get(`/api/v1/animals/${animalId}/history?hours=24`);
      setTrail(resp.data.positions || []);
      setSelectedAnimal(animalId);
    } catch {
      setTrail([]);
    }
  };

  useEffect(() => { fetchData(); }, [selectedFarm, showActiveOnly]);
  useEffect(() => {
    if (!selectedFarm) return;
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [selectedFarm]);

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

  const toggleFenceVisibility = (fenceId: string) => {
    setHiddenFences(prev => {
      const next = new Set(prev);
      if (next.has(fenceId)) {
        next.delete(fenceId);
      } else {
        next.add(fenceId);
      }
      return next;
    });
  };

  const selectFence = (fenceId: string) => {
    setSelectedFence(prev => prev === fenceId ? null : fenceId);
  };

  /**
   * Find Herdsman — zoom/animate to the first gateway with a known position
   * and show an info card with coordinates.
   */
  const findHerdsman = () => {
    const gw = gateways.find(g => g.last_latitude != null && g.last_longitude != null);
    if (!gw) return;
    setFocusedHerdsman(gw);
    setHerdsmanInfoVisible(true);
    mapRef.current?.animateToRegion({
      latitude: gw.last_latitude!,
      longitude: gw.last_longitude!,
      latitudeDelta: 0.003,
      longitudeDelta: 0.003,
    }, 800);
  };

  return (
    <View style={styles.container}>
      <MapView
        ref={mapRef}
        style={styles.map}
        initialRegion={INITIAL_REGION}
        mapType={mapType}
        showsUserLocation={false}
        showsCompass={true}
        showsScale={true}
        onPress={(e) => {
          if (sendHereMode) {
            const { latitude, longitude } = e.nativeEvent.coordinate;
            handleMapPress(latitude, longitude);
          }
        }}
      >
        {/* Farm centre location pin 📍 */}
        {selectedFarm?.latitude && selectedFarm?.longitude && (
          <Marker
            coordinate={{
              latitude: selectedFarm.latitude,
              longitude: selectedFarm.longitude,
            }}
            anchor={{ x: 0.5, y: 1 }}
            title={selectedFarm.name}
            description={`📍 ${selectedFarm.latitude.toFixed(5)}, ${selectedFarm.longitude.toFixed(5)}`}
          >
            <View style={styles.farmPin}>
              <Text style={styles.farmPinIcon}>📍</Text>
              <View style={styles.farmPinLabel}>
                <Text style={styles.farmPinName}>{selectedFarm.name}</Text>
                <Text style={styles.farmPinCoords}>
                  {selectedFarm.latitude.toFixed(5)}, {selectedFarm.longitude.toFixed(5)}
                </Text>
              </View>
            </View>
          </Marker>
        )}

        {/* Geofence polygons with labels */}
        {showGeofences && geofences.map((fence) => {
          if (!fence.geometry?.coordinates?.[0]) return null;
          if (hiddenFences.has(fence.id)) return null;
          const coords = fence.geometry.coordinates[0].map(([lon, lat]) => ({
            latitude: lat,
            longitude: lon,
          }));
          // Calculate centroid for label
          const cx = coords.reduce((s, c) => s + c.latitude, 0) / coords.length;
          const cy = coords.reduce((s, c) => s + c.longitude, 0) / coords.length;
          const isExclusion = fence.fence_type === 'exclusion';
          const isSelected = selectedFence === fence.id;
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
                fillColor={
                  isSelected
                    ? (isExclusion ? 'rgba(239,68,68,0.25)' : 'rgba(34,197,94,0.25)')
                    : (isExclusion ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)')
                }
                strokeWidth={isSelected ? 3 : 2}
                tappable={true}
                onPress={() => selectFence(fence.id)}
              />
              {/* Geofence label marker — tap to toggle visibility */}
              <Marker
                coordinate={{ latitude: cx, longitude: cy }}
                anchor={{ x: 0.5, y: 0.5 }}
                tracksViewChanges={false}
                onPress={() => selectFence(fence.id)}
              >
                <View style={[
                  styles.fenceLabel,
                  { backgroundColor: isExclusion ? '#ef4444' : '#16a34a' },
                  isSelected && styles.fenceLabelSelected,
                ]}>
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

        {/* Cattle markers — orange pin for both iOS and Android */}
        {withPosition.map((animal) => {
          // Deterministic scatter for overlapping positions (BLE animals at same gateway coords)
          let lat = animal.last_latitude!;
          let lng = animal.last_longitude!;
          const samePos = withPosition.filter(a =>
            a.last_latitude!.toFixed(5) === lat.toFixed(5) &&
            a.last_longitude!.toFixed(5) === lng.toFixed(5)
          );
          if (samePos.length > 1) {
            // Stable hash from animal ID
            let h = 0;
            for (let i = 0; i < animal.id.length; i++) {
              h = ((h << 5) - h + animal.id.charCodeAt(i)) | 0;
            }
            h = Math.abs(h);
            const angle = (h % 1000) / 1000 * Math.PI * 2;
            const radius = 0.00015 + ((h % 997) / 997) * 0.00035;
            const jitterA = angle + ((h >> 8) % 100) / 100 * 0.3;
            const jitterR = radius * (0.75 + ((h >> 16) % 100) / 100 * 0.5);
            lng += Math.cos(jitterA) * jitterR;
            lat += Math.sin(jitterA) * jitterR * 0.8;
          }

          return (
            <Marker
              key={animal.id}
              coordinate={{ latitude: lat, longitude: lng }}
              onPress={() => fetchTrail(animal.id)}
              tracksViewChanges={false}
              title={animal.name}
              description={`${animal.breed || ''} ${animal.gender === 'male' ? '♂' : animal.gender === 'female' ? '♀' : ''}\n📍 ${animal.last_latitude!.toFixed(5)}, ${animal.last_longitude!.toFixed(5)}${animal.last_speed != null ? `\nSpeed: ${animal.last_speed.toFixed(1)} km/h` : ''}`}
            >
              <View style={styles.markerPin}>
                <Text style={styles.markerEmoji}>🐄</Text>
              </View>
            </Marker>
          );
        })}

        {/* Herdsman markers — blue person icon, distinct from cattle */}
        {gateways.filter(g => g.last_latitude && g.last_longitude).map((gw) => (
          <Marker
            key={`herdsman-${gw.id}`}
            coordinate={{
              latitude: gw.last_latitude!,
              longitude: gw.last_longitude!,
            }}
            anchor={{ x: 0.5, y: 0.5 }}
            title={gw.herdsman_name || gw.name}
            description={`📡 ${gw.serial_number}\n🔋 ${gw.last_battery_pct ?? '?'}%\n📍 ${gw.last_latitude!.toFixed(5)}, ${gw.last_longitude!.toFixed(5)}`}
          >
            <View style={styles.herdsmanPin}>
              <Text style={styles.herdsmanEmoji}>🚶</Text>
            </View>
            <View style={styles.herdsmanLabel}>
              <Text style={styles.herdsmanLabelText}>{gw.herdsman_name || gw.name}</Text>
            </View>
          </Marker>
        ))}

        {/* Robotic herdsman — circular containment boundary + inner buffer band */}
        {showRobots && geofences
          .filter(f => f.shape === 'circle' && f.center_latitude != null && f.center_longitude != null && f.radius_m)
          .map((f) => {
            const center = { latitude: f.center_latitude!, longitude: f.center_longitude! };
            const buffer = f.buffer_m ?? 0;
            return (
              <React.Fragment key={`boundary-${f.id}`}>
                <Circle
                  center={center}
                  radius={f.radius_m!}
                  strokeColor="#a855f7"
                  fillColor="rgba(168,85,247,0.06)"
                  strokeWidth={2}
                />
                {buffer > 0 && (
                  <Circle
                    center={center}
                    radius={Math.max(1, f.radius_m! - buffer)}
                    strokeColor="#f59e0b"
                    fillColor="rgba(0,0,0,0)"
                    strokeWidth={1}
                  />
                )}
              </React.Fragment>
            );
          })}

        {/* Herding robot markers — purple 🤖 pin, tinted by status */}
        {showRobots && robots
          .filter(r => r.last_latitude != null && r.last_longitude != null)
          .map((r) => (
            <Marker
              key={`robot-${r.id}`}
              coordinate={{ latitude: r.last_latitude!, longitude: r.last_longitude! }}
              anchor={{ x: 0.5, y: 0.5 }}
              tracksViewChanges={false}
              onPress={() => selectRobot(r)}
            >
              <View style={[
                styles.robotPin,
                { backgroundColor: robotTint(r.status) },
                selectedRobot === r.serial_number && styles.robotPinSelected,
              ]}>
                <Text style={styles.robotEmoji}>🤖</Text>
              </View>
              <View style={styles.robotLabel}>
                <Text style={styles.robotLabelText}>{r.name} · {r.battery_pct ?? '?'}%</Text>
              </View>
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

      {/* Layer toggle button */}
      <TouchableOpacity
        style={styles.layerToggleBtn}
        onPress={() => setShowLayerPanel(!showLayerPanel)}
      >
        <Text style={styles.layerToggleBtnText}>📐</Text>
      </TouchableOpacity>

      {/* Layer panel — show/hide individual geofences */}
      {showLayerPanel && (
        <View style={styles.layerPanel}>
          <View style={styles.layerPanelHeader}>
            <Text style={styles.layerPanelTitle}>Geofences</Text>
            <TouchableOpacity onPress={() => setShowActiveOnly(!showActiveOnly)}>
              <Text style={[styles.layerToggleAll, { color: showActiveOnly ? '#10b981' : '#f59e0b' }]}>
                {showActiveOnly ? '● Active' : '✱ All'}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setShowGeofences(!showGeofences)}>
              <Text style={styles.layerToggleAll}>{showGeofences ? 'Hide All' : 'Show All'}</Text>
            </TouchableOpacity>
          </View>
          <ScrollView style={styles.layerPanelScroll}>
            {geofences.map(fence => {
              const isHidden = hiddenFences.has(fence.id);
              const isExclusion = fence.fence_type === 'exclusion';
              return (
                <TouchableOpacity
                  key={fence.id}
                  style={[styles.layerItem, isHidden && styles.layerItemHidden]}
                  onPress={() => toggleFenceVisibility(fence.id)}
                >
                  <View style={[styles.layerDot, { backgroundColor: isExclusion ? '#ef4444' : '#22c55e' }]} />
                  <Text style={[styles.layerItemText, isHidden && styles.layerItemTextHidden]}>
                    {fence.name}
                  </Text>
                  <Text style={styles.layerItemIcon}>{isHidden ? '👁️‍🗨️' : '👁️'}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>
      )}

      {/* Selected fence info card */}
      {selectedFence && (
        <View style={styles.fenceInfoCard}>
          {(() => {
            const fence = geofences.find(f => f.id === selectedFence);
            if (!fence) return null;
            const isExclusion = fence.fence_type === 'exclusion';
            const areaText = fence.area_hectares
              ? fence.area_hectares >= 100 ? `${(fence.area_hectares/100).toFixed(0)} km²`
                : fence.area_hectares >= 1 ? `${fence.area_hectares.toFixed(1)} ha`
                : `${Math.round(fence.area_hectares * 10000)} m²`
              : '';
            return (
              <>
                <View style={styles.fenceInfoHeader}>
                  <View style={[styles.fenceInfoDot, { backgroundColor: isExclusion ? '#ef4444' : '#22c55e' }]} />
                  <Text style={styles.fenceInfoName}>{fence.name}</Text>
                  <TouchableOpacity onPress={() => setSelectedFence(null)}>
                    <Text style={styles.fenceInfoClose}>✕</Text>
                  </TouchableOpacity>
                </View>
                <Text style={styles.fenceInfoDetail}>
                  {isExclusion ? '🚫 Exclusion Zone' : '✅ Inclusion Zone'}
                  {areaText ? ` · ${areaText}` : ''}
                </Text>
                <TouchableOpacity
                  style={styles.fenceInfoHideBtn}
                  onPress={() => { toggleFenceVisibility(fence.id); setSelectedFence(null); }}
                >
                  <Text style={styles.fenceInfoHideBtnText}>
                    {hiddenFences.has(fence.id) ? 'Show on Map' : 'Hide from Map'}
                  </Text>
                </TouchableOpacity>
              </>
            );
          })()}
        </View>
      )}

      {/* Trail info */}
      {selectedAnimal && trail.length > 0 && (
        <TouchableOpacity style={styles.trailInfo} onPress={() => { setTrail([]); setSelectedAnimal(null); }}>
          <Text style={styles.trailInfoText}>📍 Trail: {trail.length} pts · Tap to clear</Text>
        </TouchableOpacity>
      )}

      {/* Find Herdsman button */}
      {gateways.some(g => g.last_latitude && g.last_longitude) && (
        <TouchableOpacity
          style={styles.findHerdsmanBtn}
          onPress={findHerdsman}
          accessibilityLabel="Find herdsman on map"
        >
          <Text style={styles.findHerdsmanIcon}>🚶</Text>
          <Text style={styles.findHerdsmanLabel}>Find</Text>
        </TouchableOpacity>
      )}

      {/* Herdsman info card — shows after navigating to herdsman */}
      {herdsmanInfoVisible && focusedHerdsman && (
        <View style={styles.herdsmanInfoCard}>
          <View style={styles.herdsmanInfoHeader}>
            <View style={styles.herdsmanInfoDot} />
            <Text style={styles.herdsmanInfoName}>
              {focusedHerdsman.herdsman_name || focusedHerdsman.name}
            </Text>
            <TouchableOpacity onPress={() => setHerdsmanInfoVisible(false)}>
              <Text style={styles.herdsmanInfoClose}>✕</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.herdsmanInfoCoords}>
            📍 {focusedHerdsman.last_latitude!.toFixed(5)}, {focusedHerdsman.last_longitude!.toFixed(5)}
          </Text>
          <Text style={styles.herdsmanInfoDetail}>
            📡 {focusedHerdsman.serial_number} · 🔋 {focusedHerdsman.last_battery_pct ?? '?'}%
          </Text>
          {focusedHerdsman.last_seen && (
            <Text style={styles.herdsmanInfoSeen}>
              Last seen: {new Date(focusedHerdsman.last_seen).toLocaleTimeString()}
            </Text>
          )}
        </View>
      )}

      {/* Send-here mode banner — active while waiting for a map tap */}
      {sendHereMode && focusedRobot && (
        <View style={styles.sendHereBanner}>
          <Text style={styles.sendHereBannerText}>
            Tap the map to send {focusedRobot.name} there
          </Text>
          <TouchableOpacity onPress={() => setSendHereMode(false)}>
            <Text style={styles.sendHereBannerCancel}>Cancel</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Per-robot action card — manual override commands */}
      {focusedRobot && (
        <View style={styles.robotCard}>
          <View style={styles.robotCardHeader}>
            <View style={[styles.robotCardDot, { backgroundColor: robotTint(focusedRobot.status) }]} />
            <Text style={styles.robotCardName}>{focusedRobot.name}</Text>
            <TouchableOpacity onPress={() => { setSelectedRobot(null); setSendHereMode(false); }}>
              <Text style={styles.robotCardClose}>✕</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.robotCardDetail}>
            {focusedRobot.serial_number} · {focusedRobot.model} · {focusedRobot.status} · 🔋 {focusedRobot.battery_pct ?? '?'}%
          </Text>
          <View style={styles.robotCardActions}>
            <TouchableOpacity
              style={[styles.robotActionBtn, sendHereMode && styles.robotActionBtnActive]}
              disabled={robotBusy}
              onPress={() => setSendHereMode(v => !v)}
            >
              <Text style={styles.robotActionText}>📍 Send here</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.robotActionBtn}
              disabled={robotBusy}
              onPress={() => handleRobotCommand('return_home')}
            >
              <Text style={styles.robotActionText}>🏠 Return</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.robotActionBtn}
              disabled={robotBusy}
              onPress={() => handleRobotCommand('patrol')}
            >
              <Text style={styles.robotActionText}>🔄 Patrol</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.robotActionBtn, styles.robotActionBtnStop]}
              disabled={robotBusy}
              onPress={() => handleRobotCommand('stop')}
            >
              <Text style={styles.robotActionText}>⛔ Stop</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Herding fleet button — only shown when this farm has a robot fleet */}
      {robots.length > 0 && (
        <TouchableOpacity
          style={[styles.herdingBtn, showHerdingPanel && styles.herdingBtnActive]}
          onPress={() => setShowHerdingPanel(v => !v)}
          accessibilityLabel="Robotic herdsman fleet"
        >
          <Text style={styles.herdingIcon}>🤖</Text>
          <Text style={styles.herdingLabel}>Fleet</Text>
        </TouchableOpacity>
      )}

      {/* Herding fleet panel — status summary + layer toggle + STOP ALL */}
      {showHerdingPanel && robots.length > 0 && (
        <View style={styles.herdingPanel}>
          <View style={styles.herdingPanelHeader}>
            <Text style={styles.herdingPanelTitle}>🤖 Herding Fleet</Text>
            <TouchableOpacity onPress={() => setShowHerdingPanel(false)}>
              <Text style={styles.herdingPanelClose}>✕</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.herdingStatsRow}>
            <View style={styles.herdingStat}>
              <Text style={styles.herdingStatNum}>{herding?.robots_total ?? robots.length}</Text>
              <Text style={styles.herdingStatLbl}>Robots</Text>
            </View>
            <View style={styles.herdingStat}>
              <Text style={[styles.herdingStatNum, { color: '#db2777' }]}>{herding?.robots_active ?? 0}</Text>
              <Text style={styles.herdingStatLbl}>Active</Text>
            </View>
            <View style={styles.herdingStat}>
              <Text style={[styles.herdingStatNum, { color: '#c4b5fd' }]}>{herding?.robots_charging ?? 0}</Text>
              <Text style={styles.herdingStatLbl}>Charging</Text>
            </View>
            <View style={styles.herdingStat}>
              <Text style={[styles.herdingStatNum, { color: '#f59e0b' }]}>{herding?.active_jobs ?? 0}</Text>
              <Text style={styles.herdingStatLbl}>Jobs</Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.herdingLayerToggle}
            onPress={() => setShowRobots(v => !v)}
          >
            <Text style={styles.herdingLayerToggleText}>
              {showRobots ? '👁️ Robots shown' : '👁️‍🗨️ Robots hidden'}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.stopAllBtn, stopping && styles.stopAllBtnDisabled]}
            onPress={handleStopAll}
            disabled={stopping}
          >
            <Text style={styles.stopAllBtnText}>{stopping ? 'Stopping…' : '⛔ STOP ALL'}</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Overlay: count */}
      <View style={styles.overlay}>
        <Text style={styles.overlayText}>
          🐄 {withPosition.length} tracked
          {robots.length > 0 ? ` · 🤖 ${robots.length}` : ''} · Updates every 30s
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  map: { flex: 1 },
  markerPin: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: '#ea580c',
    borderWidth: 2, borderColor: '#fff',
    alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 3, elevation: 5,
  },
  markerEmoji: { fontSize: 14 },
  herdsmanPin: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: '#2563eb',
    borderWidth: 2, borderColor: '#fff',
    alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 3, elevation: 5,
  },
  herdsmanEmoji: { fontSize: 16 },
  herdsmanLabel: {
    backgroundColor: '#1d4ed8', paddingHorizontal: 5, paddingVertical: 1,
    borderRadius: 3, marginTop: 2, alignItems: 'center',
  },
  herdsmanLabelText: { color: '#fff', fontSize: 9, fontWeight: 'bold' },
  farmPin: { alignItems: 'center' },
  farmPinIcon: { fontSize: 28 },
  farmPinLabel: {
    backgroundColor: '#1d4ed8', paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: 4, marginTop: -4, alignItems: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.3, shadowRadius: 2, elevation: 3,
  },
  farmPinName: { color: '#fff', fontSize: 10, fontWeight: 'bold' },
  farmPinCoords: { color: '#93c5fd', fontSize: 8 },
  fenceLabel: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  fenceLabelSelected: { borderWidth: 2, borderColor: '#fff', transform: [{ scale: 1.1 }] },
  fenceLabelText: { color: '#fff', fontSize: 9, fontWeight: 'bold' },
  mapTypeSwitcher: {
    position: 'absolute', top: 60, right: 12,
    backgroundColor: 'rgba(0,0,0,0.7)', borderRadius: 8,
    flexDirection: 'column', padding: 4, gap: 4,
  },
  mapTypeBtn: { padding: 6, borderRadius: 6 },
  mapTypeBtnActive: { backgroundColor: '#22c55e' },
  mapTypeBtnText: { fontSize: 18 },
  mapTypeBtnTextActive: {},
  // Layer toggle button
  layerToggleBtn: {
    position: 'absolute', top: 60, left: 12,
    backgroundColor: 'rgba(0,0,0,0.7)', borderRadius: 8,
    padding: 8,
  },
  layerToggleBtnText: { fontSize: 18 },
  // Layer panel
  layerPanel: {
    position: 'absolute', top: 105, left: 12,
    backgroundColor: 'rgba(17,24,39,0.95)', borderRadius: 10,
    width: 200, maxHeight: 280, padding: 8,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 4, elevation: 5,
  },
  layerPanelHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 6, paddingBottom: 4, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.1)',
  },
  layerPanelTitle: { color: '#fff', fontSize: 12, fontWeight: 'bold' },
  layerToggleAll: { color: '#60a5fa', fontSize: 10, fontWeight: '600' },
  layerPanelScroll: { maxHeight: 220 },
  layerItem: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 6, paddingHorizontal: 4,
    borderRadius: 4,
  },
  layerItemHidden: { opacity: 0.4 },
  layerDot: { width: 8, height: 8, borderRadius: 4, marginRight: 8 },
  layerItemText: { color: '#fff', fontSize: 11, flex: 1 },
  layerItemTextHidden: { textDecorationLine: 'line-through' },
  layerItemIcon: { fontSize: 12 },
  // Selected fence info card
  fenceInfoCard: {
    position: 'absolute', bottom: 120, left: 16, right: 16,
    backgroundColor: 'rgba(17,24,39,0.95)', borderRadius: 12,
    padding: 12,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 4, elevation: 5,
  },
  fenceInfoHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 4 },
  fenceInfoDot: { width: 10, height: 10, borderRadius: 5, marginRight: 8 },
  fenceInfoName: { color: '#fff', fontSize: 14, fontWeight: 'bold', flex: 1 },
  fenceInfoClose: { color: '#9ca3af', fontSize: 16, paddingHorizontal: 4 },
  fenceInfoDetail: { color: '#d1d5db', fontSize: 11, marginBottom: 8 },
  fenceInfoHideBtn: {
    backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 6, paddingVertical: 6, alignItems: 'center',
  },
  fenceInfoHideBtnText: { color: '#60a5fa', fontSize: 11, fontWeight: '600' },
  trailInfo: {
    position: 'absolute', top: 60, left: 56,
    backgroundColor: '#7c3aed', borderRadius: 8, padding: 8,
  },
  trailInfoText: { color: '#fff', fontSize: 11, fontWeight: '600' },
  overlay: {
    position: 'absolute', bottom: 80, left: 16, right: 16,
    backgroundColor: 'rgba(0,0,0,0.7)', borderRadius: 8, padding: 8, alignItems: 'center',
  },
  overlayText: { color: '#fff', fontSize: 12 },
  // Find Herdsman button
  findHerdsmanBtn: {
    position: 'absolute', bottom: 140, right: 12,
    backgroundColor: '#2563eb', borderRadius: 24,
    width: 48, height: 48, alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4, shadowRadius: 4, elevation: 6,
  },
  findHerdsmanIcon: { fontSize: 18, marginTop: -2 },
  findHerdsmanLabel: { fontSize: 8, color: '#bfdbfe', fontWeight: '600', marginTop: -2 },
  // Herdsman info card
  herdsmanInfoCard: {
    position: 'absolute', bottom: 120, left: 16, right: 16,
    backgroundColor: 'rgba(17,24,39,0.95)', borderRadius: 12,
    padding: 12, borderLeftWidth: 3, borderLeftColor: '#2563eb',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 4, elevation: 5,
  },
  herdsmanInfoHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  herdsmanInfoDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#2563eb', marginRight: 8 },
  herdsmanInfoName: { color: '#fff', fontSize: 14, fontWeight: 'bold', flex: 1 },
  herdsmanInfoClose: { color: '#9ca3af', fontSize: 16, paddingHorizontal: 4 },
  herdsmanInfoCoords: { color: '#93c5fd', fontSize: 12, fontWeight: '600', marginBottom: 4 },
  herdsmanInfoDetail: { color: '#d1d5db', fontSize: 11, marginBottom: 2 },
  herdsmanInfoSeen: { color: '#6b7280', fontSize: 10 },
  // Robot markers
  robotPin: {
    width: 30, height: 30, borderRadius: 8,
    borderWidth: 2, borderColor: '#fff',
    alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 3, elevation: 5,
  },
  robotPinSelected: { borderColor: '#fde047', borderWidth: 3, transform: [{ scale: 1.15 }] },
  robotEmoji: { fontSize: 15 },
  robotLabel: {
    backgroundColor: '#7e22ce', paddingHorizontal: 5, paddingVertical: 1,
    borderRadius: 3, marginTop: 2, alignItems: 'center',
  },
  robotLabelText: { color: '#fff', fontSize: 9, fontWeight: 'bold' },
  // Send-here mode banner
  sendHereBanner: {
    position: 'absolute', top: 60, left: 56, right: 56,
    backgroundColor: '#a855f7', borderRadius: 8, padding: 8,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 4, elevation: 5,
  },
  sendHereBannerText: { color: '#fff', fontSize: 11, fontWeight: '600', flex: 1 },
  sendHereBannerCancel: { color: '#fde047', fontSize: 11, fontWeight: 'bold', paddingLeft: 8 },
  // Per-robot action card
  robotCard: {
    position: 'absolute', bottom: 120, left: 16, right: 16,
    backgroundColor: 'rgba(17,24,39,0.97)', borderRadius: 12,
    padding: 12, borderLeftWidth: 3, borderLeftColor: '#a855f7',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 4, elevation: 5,
  },
  robotCardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 4 },
  robotCardDot: { width: 10, height: 10, borderRadius: 5, marginRight: 8 },
  robotCardName: { color: '#fff', fontSize: 14, fontWeight: 'bold', flex: 1 },
  robotCardClose: { color: '#9ca3af', fontSize: 16, paddingHorizontal: 4 },
  robotCardDetail: { color: '#d1d5db', fontSize: 11, marginBottom: 10 },
  robotCardActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  robotActionBtn: {
    backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 6,
    paddingVertical: 8, paddingHorizontal: 10, flexGrow: 1, alignItems: 'center',
  },
  robotActionBtnActive: { backgroundColor: '#a855f7' },
  robotActionBtnStop: { backgroundColor: 'rgba(220,38,38,0.85)' },
  robotActionText: { color: '#fff', fontSize: 11, fontWeight: '600' },
  // Herding fleet button (above Find Herdsman FAB)
  herdingBtn: {
    position: 'absolute', bottom: 196, right: 12,
    backgroundColor: '#7e22ce', borderRadius: 24,
    width: 48, height: 48, alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4, shadowRadius: 4, elevation: 6,
  },
  herdingBtnActive: { backgroundColor: '#a855f7' },
  herdingIcon: { fontSize: 18, marginTop: -2 },
  herdingLabel: { fontSize: 8, color: '#e9d5ff', fontWeight: '600', marginTop: -2 },
  // Herding fleet panel
  herdingPanel: {
    position: 'absolute', bottom: 120, left: 16, right: 16,
    backgroundColor: 'rgba(17,24,39,0.97)', borderRadius: 12,
    padding: 12, borderLeftWidth: 3, borderLeftColor: '#a855f7',
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 4, elevation: 5,
  },
  herdingPanelHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  herdingPanelTitle: { color: '#fff', fontSize: 14, fontWeight: 'bold' },
  herdingPanelClose: { color: '#9ca3af', fontSize: 16, paddingHorizontal: 4 },
  herdingStatsRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 },
  herdingStat: { alignItems: 'center', flex: 1 },
  herdingStatNum: { color: '#fff', fontSize: 18, fontWeight: 'bold' },
  herdingStatLbl: { color: '#9ca3af', fontSize: 10, marginTop: 2 },
  herdingLayerToggle: {
    backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 6,
    paddingVertical: 7, alignItems: 'center', marginBottom: 8,
  },
  herdingLayerToggleText: { color: '#d8b4fe', fontSize: 11, fontWeight: '600' },
  stopAllBtn: {
    backgroundColor: '#dc2626', borderRadius: 8, paddingVertical: 10, alignItems: 'center',
  },
  stopAllBtnDisabled: { opacity: 0.6 },
  stopAllBtnText: { color: '#fff', fontSize: 13, fontWeight: 'bold', letterSpacing: 0.5 },
});
