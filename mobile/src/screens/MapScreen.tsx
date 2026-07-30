import React from 'react';
import { View, StyleSheet, Platform } from 'react-native';

/**
 * Map Screen — embeds the full interactive web dashboard map.
 * Shows the same map as the web dashboard: tiles, geofences, cattle markers, trails.
 *
 * On web: renders as an iframe pointing to the dashboard map page.
 * On native: would use react-native-webview (same approach).
 */

const MAP_URL = 'http://localhost:5173';

export default function MapScreen() {
  if (Platform.OS === 'web') {
    return (
      <View style={styles.container}>
        <iframe
          src={MAP_URL}
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            borderRadius: 0,
          }}
          title="LivestockGuard Map"
          allow="geolocation"
        />
      </View>
    );
  }

  // Native: would use react-native-webview
  return (
    <View style={styles.container}>
      <View style={styles.placeholder}>
        {/* On native builds, use: <WebView source={{ uri: MAP_URL }} /> */}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  placeholder: { flex: 1, justifyContent: 'center', alignItems: 'center' },
});
