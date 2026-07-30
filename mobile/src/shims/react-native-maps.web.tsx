/**
 * Web shim for react-native-maps
 * On web, we render a placeholder since Google Maps native views aren't available.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

const MapView = ({ children, style, ...props }: any) => (
  <View style={[styles.container, style]}>
    <Text style={styles.text}>Map (native only — use web dashboard for map view)</Text>
    {children}
  </View>
);

const Marker = (_props: any) => null;
const Polyline = (_props: any) => null;
const Polygon = (_props: any) => null;
const Circle = (_props: any) => null;
const Callout = (_props: any) => null;

MapView.Marker = Marker;
MapView.Polyline = Polyline;
MapView.Polygon = Polygon;
MapView.Circle = Circle;
MapView.Callout = Callout;

export default MapView;
export { Marker, Polyline, Polygon, Circle, Callout };

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1f2937',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#374151',
  },
  text: {
    color: '#9ca3af',
    fontSize: 14,
  },
});
