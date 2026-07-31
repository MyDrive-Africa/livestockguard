import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { bleScanner } from '../services/bleScanner';
import { useFarm } from '../context/FarmContext';

/**
 * Herdsman view — farm-aware with cumulative daily scan tracking.
 *
 * Shows:
 * - In Range (now): instant BLE count
 * - Seen Today: cumulative unique tags since shift start
 * - Not Seen Today: concern list — never detected all day
 * - Patrol mode vs Kraal mode UI
 */
export default function HerdsmanScreen() {
  const { selectedFarm } = useFarm();
  const [cattleInRange, setCattleInRange] = useState(0);
  const [totalRegistered, setTotalRegistered] = useState(0);
  const [seenToday, setSeenToday] = useState(0);
  const [notSeenToday, setNotSeenToday] = useState<string[]>([]);
  const [missing, setMissing] = useState<string[]>([]);
  const [scannerActive, setScannerActive] = useState(false);
  const [shiftActive, setShiftActive] = useState(false);
  const [mode, setMode] = useState<'patrol' | 'kraal' | 'idle'>('idle');
  const [lastNewTag, setLastNewTag] = useState<string>('');

  useEffect(() => {
    if (!selectedFarm) return;

    async function startScanner() {
      await bleScanner.init(selectedFarm!.id);
      bleScanner.start();
      setScannerActive(true);
      setTotalRegistered(bleScanner.getTotalRegistered());
      setShiftActive(bleScanner.isShiftActive());
      setMode(bleScanner.getMode());
    }
    startScanner();

    const interval = setInterval(() => {
      setCattleInRange(bleScanner.getCattleInRange());
      setTotalRegistered(bleScanner.getTotalRegistered());
      setSeenToday(bleScanner.getSeenTodayCount());
      setNotSeenToday(bleScanner.getNotSeenToday());
      setMissing(bleScanner.getMissing());
      setShiftActive(bleScanner.isShiftActive());
      setMode(bleScanner.getMode());

      const lastTime = bleScanner.getLastNewTagTime();
      if (lastTime) {
        const h = lastTime.getHours().toString().padStart(2, '0');
        const m = lastTime.getMinutes().toString().padStart(2, '0');
        setLastNewTag(`${h}:${m}`);
      }
    }, 5000);

    return () => {
      clearInterval(interval);
      bleScanner.stop();
    };
  }, [selectedFarm]);

  const handleStartShift = async () => {
    await bleScanner.startShift();
    setShiftActive(true);
    setMode('patrol');
    setSeenToday(bleScanner.getSeenTodayCount());
  };

  const handleEndShift = async () => {
    await bleScanner.endShift();
    setMode('kraal');
  };

  const seenPct = totalRegistered > 0 ? Math.round((seenToday / totalRegistered) * 100) : 0;
  const allSeenToday = seenToday >= totalRegistered && totalRegistered > 0;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Farm name */}
      <View style={styles.farmBadge}>
        <Text style={styles.farmBadgeText}>{selectedFarm?.name || 'No farm'}</Text>
      </View>

      {/* Scanner status */}
      <View style={[styles.statusBar, { backgroundColor: scannerActive ? '#16a34a' : '#ef4444' }]}>
        <Text style={styles.statusText}>
          {scannerActive ? '📶 Scanner Active' : '❌ Scanner Off'}
          {shiftActive && ` · ${mode === 'kraal' ? 'Kraal Check' : 'On Patrol'}`}
        </Text>
      </View>

      {/* Main count — In Range NOW */}
      <View style={styles.countContainer}>
        <Text style={styles.countNumber}>{cattleInRange}</Text>
        <Text style={styles.countLabel}>/ {totalRegistered} in range now</Text>
      </View>

      {/* Cumulative Seen Today — the key new feature */}
      {shiftActive && (
        <View style={styles.seenTodayCard}>
          <View style={styles.seenTodayHeader}>
            <Text style={styles.seenTodayTitle}>📋 Seen Today (Cumulative)</Text>
            <Text style={styles.seenTodayPct}>{seenPct}%</Text>
          </View>

          {/* Progress bar */}
          <View style={styles.progressBar}>
            <View style={[
              styles.progressFill,
              { width: `${seenPct}%` },
              seenPct >= 90 ? styles.progressGreen : seenPct >= 70 ? styles.progressYellow : styles.progressRed,
            ]} />
          </View>

          <Text style={styles.seenTodayCount}>
            {seenToday} / {totalRegistered} unique tags detected
          </Text>

          {lastNewTag ? (
            <Text style={styles.lastNewText}>Last new tag: {lastNewTag}</Text>
          ) : null}

          {/* All seen today = green checkmark */}
          {allSeenToday && (
            <View style={styles.allSeenBadge}>
              <Text style={styles.allSeenText}>✓ All cattle seen today</Text>
            </View>
          )}
        </View>
      )}

      {/* Not Seen Today — concern list */}
      {shiftActive && notSeenToday.length > 0 && (
        <View style={styles.notSeenCard}>
          <Text style={styles.notSeenTitle}>
            ⚠️ Not Seen Today ({notSeenToday.length})
          </Text>
          <Text style={styles.notSeenSubtitle}>
            Never detected since shift start
          </Text>
          {notSeenToday.slice(0, 8).map((name, i) => (
            <View key={i} style={styles.notSeenItem}>
              <Text style={styles.notSeenDot}>•</Text>
              <Text style={styles.notSeenName}>{name}</Text>
            </View>
          ))}
          {notSeenToday.length > 8 && (
            <Text style={styles.notSeenMore}>+{notSeenToday.length - 8} more</Text>
          )}
        </View>
      )}

      {/* Kraal mode — evening verification */}
      {mode === 'kraal' && (
        <View style={styles.kraalCard}>
          <Text style={styles.kraalTitle}>🏠 Kraal Verification</Text>
          <Text style={styles.kraalCount}>
            {cattleInRange} / {totalRegistered} in kraal now
          </Text>
          {cattleInRange >= totalRegistered ? (
            <Text style={styles.kraalOk}>✓ All cattle accounted for</Text>
          ) : (
            <Text style={styles.kraalWarning}>
              ⚠️ {totalRegistered - cattleInRange} missing from kraal
            </Text>
          )}
          <Text style={styles.kraalDeparture}>
            Departure count: {bleScanner.getDepartureCount()}
          </Text>
        </View>
      )}

      {/* Shift controls */}
      <View style={styles.shiftControls}>
        {!shiftActive ? (
          <TouchableOpacity style={styles.startShiftBtn} onPress={handleStartShift}>
            <Text style={styles.shiftBtnText}>▶ Start Shift</Text>
          </TouchableOpacity>
        ) : mode === 'patrol' ? (
          <TouchableOpacity style={styles.endShiftBtn} onPress={handleEndShift}>
            <Text style={styles.shiftBtnText}>🏠 Kraal Check (End Patrol)</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={styles.startShiftBtn} onPress={handleStartShift}>
            <Text style={styles.shiftBtnText}>↺ New Shift</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Footer */}
      <Text style={styles.footer}>
        BLE scan every 8s · {totalRegistered > 20 ? 'Large herd — variable range' : 'Small herd — close range'}
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  content: { alignItems: 'center', paddingTop: 60, paddingBottom: 40, paddingHorizontal: 20 },
  farmBadge: { backgroundColor: '#374151', paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12, marginBottom: 12 },
  farmBadgeText: { color: '#9ca3af', fontSize: 12, fontWeight: '500' },
  statusBar: { width: '100%', padding: 8, borderRadius: 8, alignItems: 'center', marginBottom: 24 },
  statusText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  countContainer: { alignItems: 'center', marginBottom: 20 },
  countNumber: { fontSize: 80, fontWeight: 'bold', color: '#22c55e' },
  countLabel: { fontSize: 16, color: '#9ca3af' },

  // Seen Today card
  seenTodayCard: { width: '100%', backgroundColor: '#1f2937', borderRadius: 12, padding: 16, marginBottom: 12 },
  seenTodayHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  seenTodayTitle: { color: '#f9fafb', fontSize: 14, fontWeight: '600' },
  seenTodayPct: { color: '#22c55e', fontSize: 18, fontWeight: 'bold' },
  progressBar: { height: 8, backgroundColor: '#374151', borderRadius: 4, overflow: 'hidden', marginBottom: 8 },
  progressFill: { height: '100%', borderRadius: 4 },
  progressGreen: { backgroundColor: '#22c55e' },
  progressYellow: { backgroundColor: '#f59e0b' },
  progressRed: { backgroundColor: '#ef4444' },
  seenTodayCount: { color: '#9ca3af', fontSize: 13 },
  lastNewText: { color: '#6b7280', fontSize: 11, marginTop: 4 },
  allSeenBadge: { backgroundColor: '#14532d', borderRadius: 8, padding: 8, marginTop: 8, alignItems: 'center' },
  allSeenText: { color: '#86efac', fontSize: 13, fontWeight: '600' },

  // Not Seen Today card
  notSeenCard: { width: '100%', backgroundColor: '#7f1d1d', borderRadius: 12, padding: 16, marginBottom: 12 },
  notSeenTitle: { color: '#fca5a5', fontSize: 14, fontWeight: '600' },
  notSeenSubtitle: { color: '#fca5a5', fontSize: 11, opacity: 0.7, marginBottom: 8 },
  notSeenItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 2 },
  notSeenDot: { color: '#fca5a5', fontSize: 14, marginRight: 8 },
  notSeenName: { color: '#fca5a5', fontSize: 13 },
  notSeenMore: { color: '#fca5a5', fontSize: 11, opacity: 0.6, marginTop: 4 },

  // Kraal card
  kraalCard: { width: '100%', backgroundColor: '#1e3a5f', borderRadius: 12, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#3b82f6' },
  kraalTitle: { color: '#93c5fd', fontSize: 14, fontWeight: '600', marginBottom: 8 },
  kraalCount: { color: '#f9fafb', fontSize: 16, fontWeight: 'bold', marginBottom: 4 },
  kraalOk: { color: '#86efac', fontSize: 13, fontWeight: '600' },
  kraalWarning: { color: '#fca5a5', fontSize: 13, fontWeight: '600' },
  kraalDeparture: { color: '#6b7280', fontSize: 11, marginTop: 8 },

  // Shift controls
  shiftControls: { width: '100%', marginTop: 8, marginBottom: 16 },
  startShiftBtn: { backgroundColor: '#16a34a', borderRadius: 10, padding: 14, alignItems: 'center' },
  endShiftBtn: { backgroundColor: '#2563eb', borderRadius: 10, padding: 14, alignItems: 'center' },
  shiftBtnText: { color: '#fff', fontSize: 15, fontWeight: '600' },

  footer: { color: '#4b5563', fontSize: 11, textAlign: 'center', marginTop: 8 },
});
