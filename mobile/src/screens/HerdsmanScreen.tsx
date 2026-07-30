import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { bleScanner } from '../services/bleScanner';

/**
 * Herdsman view — simple cattle count and scanner status.
 * This is what the herdsman sees if they open the app.
 * The BLE scanner runs in the background regardless.
 */
export default function HerdsmanScreen() {
  const [cattleInRange, setCattleInRange] = useState(0);
  const [totalRegistered, setTotalRegistered] = useState(0);
  const [scannerActive, setScannerActive] = useState(false);
  const [missing, setMissing] = useState<string[]>([]);

  useEffect(() => {
    async function startScanner() {
      await bleScanner.init();
      bleScanner.start();
      setScannerActive(true);
      setTotalRegistered(bleScanner.getTotalRegistered());
    }
    startScanner();

    const interval = setInterval(() => {
      setCattleInRange(bleScanner.getCattleInRange());
      setTotalRegistered(bleScanner.getTotalRegistered());
      setMissing(bleScanner.getMissing());
    }, 5000);

    return () => {
      clearInterval(interval);
      bleScanner.stop();
    };
  }, []);

  const allAccountedFor = cattleInRange >= totalRegistered && totalRegistered > 0;
  const missingCount = totalRegistered - cattleInRange;

  return (
    <View style={styles.container}>
      {/* Status */}
      <View style={[styles.statusBar, { backgroundColor: scannerActive ? '#16a34a' : '#ef4444' }]}>
        <Text style={styles.statusText}>
          {scannerActive ? '📶 Scanner Active' : '❌ Scanner Off'}
        </Text>
      </View>

      {/* Cattle Count */}
      <View style={styles.countContainer}>
        <Text style={styles.countNumber}>{cattleInRange}</Text>
        <Text style={styles.countLabel}>/ {totalRegistered} cattle in range</Text>
      </View>

      {/* Status Message */}
      {allAccountedFor ? (
        <View style={styles.allGood}>
          <Text style={styles.allGoodText}>✓ All cattle accounted for</Text>
        </View>
      ) : missing.length > 0 ? (
        <View style={styles.warning}>
          <Text style={styles.warningText}>⚠️ {missing.length} cattle not detected</Text>
          <Text style={styles.missingList}>{missing.slice(0, 5).join(', ')}</Text>
        </View>
      ) : (
        <View style={styles.info}>
          <Text style={styles.infoText}>Scanning for cattle...</Text>
        </View>
      )}

      {/* Footer */}
      <Text style={styles.footer}>
        BLE scan every 5s · GPS every 30s · Batch every 25s
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827', justifyContent: 'center', alignItems: 'center' },
  statusBar: { position: 'absolute', top: 60, left: 20, right: 20, padding: 8, borderRadius: 8, alignItems: 'center' },
  statusText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  countContainer: { alignItems: 'center', marginBottom: 24 },
  countNumber: { fontSize: 96, fontWeight: 'bold', color: '#22c55e' },
  countLabel: { fontSize: 18, color: '#9ca3af' },
  allGood: { backgroundColor: '#14532d', padding: 16, borderRadius: 12, marginHorizontal: 20 },
  allGoodText: { color: '#86efac', fontSize: 16, textAlign: 'center', fontWeight: '600' },
  warning: { backgroundColor: '#7f1d1d', padding: 16, borderRadius: 12, marginHorizontal: 20 },
  warningText: { color: '#fca5a5', fontSize: 16, textAlign: 'center', fontWeight: '600' },
  missingList: { color: '#fca5a5', fontSize: 12, textAlign: 'center', marginTop: 4, opacity: 0.8 },
  info: { padding: 16 },
  infoText: { color: '#6b7280', fontSize: 14, textAlign: 'center' },
  footer: { position: 'absolute', bottom: 40, color: '#4b5563', fontSize: 12 },
});
