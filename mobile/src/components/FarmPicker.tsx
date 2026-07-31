import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  Modal,
  FlatList,
  StyleSheet,
  SafeAreaView,
} from 'react-native';
import { useFarm } from '../context/FarmContext';

interface FarmPickerProps {
  role: string;
}

/**
 * Persistent header bar showing the current farm name with a dropdown picker.
 * - Admin: shows all farms with search (future)
 * - Farm Owner / Viewer: shows assigned farms
 * - Herdsman: static text, no picker interaction
 */
export default function FarmPicker({ role }: FarmPickerProps) {
  const { farms, selectedFarm, loading, switchFarm } = useFarm();
  const [modalVisible, setModalVisible] = useState(false);

  // Herdsman can't switch — show static farm name
  const isLocked = role === 'herdsman' && farms.length <= 1;

  if (loading) {
    return (
      <View style={styles.container}>
        <Text style={styles.loadingText}>Loading farms...</Text>
      </View>
    );
  }

  if (!selectedFarm) {
    return (
      <View style={styles.container}>
        <Text style={styles.loadingText}>No farms available</Text>
      </View>
    );
  }

  const handleSelect = (farmId: string) => {
    switchFarm(farmId);
    setModalVisible(false);
  };

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={styles.picker}
        onPress={() => !isLocked && setModalVisible(true)}
        activeOpacity={isLocked ? 1 : 0.7}
        accessibilityRole="button"
        accessibilityLabel={`Current farm: ${selectedFarm.name}. ${isLocked ? '' : 'Tap to switch farm.'}`}
      >
        <View style={styles.farmInfo}>
          <Text style={styles.farmLabel}>Farm</Text>
          <Text style={styles.farmName} numberOfLines={1}>
            {selectedFarm.name}
          </Text>
        </View>
        {!isLocked && (
          <Text style={styles.chevron}>▼</Text>
        )}
      </TouchableOpacity>

      {/* Farm selection modal */}
      <Modal
        visible={modalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <SafeAreaView style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Farm</Text>
              <TouchableOpacity
                onPress={() => setModalVisible(false)}
                accessibilityRole="button"
                accessibilityLabel="Close farm picker"
              >
                <Text style={styles.modalClose}>✕</Text>
              </TouchableOpacity>
            </View>

            <FlatList
              data={farms}
              keyExtractor={(item) => item.id}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.farmItem,
                    item.id === selectedFarm.id && styles.farmItemActive,
                  ]}
                  onPress={() => handleSelect(item.id)}
                  accessibilityRole="button"
                  accessibilityLabel={`Select ${item.name}`}
                >
                  <Text
                    style={[
                      styles.farmItemText,
                      item.id === selectedFarm.id && styles.farmItemTextActive,
                    ]}
                  >
                    {item.name}
                  </Text>
                  {item.location && (
                    <Text style={styles.farmItemLocation}>{item.location}</Text>
                  )}
                  {item.id === selectedFarm.id && (
                    <Text style={styles.checkmark}>✓</Text>
                  )}
                </TouchableOpacity>
              )}
              contentContainerStyle={styles.farmList}
            />
          </SafeAreaView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1f2937',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#374151',
  },
  loadingText: {
    color: '#6b7280',
    fontSize: 13,
    textAlign: 'center',
  },
  picker: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  farmInfo: {
    flex: 1,
  },
  farmLabel: {
    color: '#6b7280',
    fontSize: 11,
    fontWeight: '500',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  farmName: {
    color: '#f9fafb',
    fontSize: 16,
    fontWeight: '700',
    marginTop: 2,
  },
  chevron: {
    color: '#22c55e',
    fontSize: 12,
    marginLeft: 8,
  },
  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#111827',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '60%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#374151',
  },
  modalTitle: {
    color: '#f9fafb',
    fontSize: 18,
    fontWeight: '700',
  },
  modalClose: {
    color: '#9ca3af',
    fontSize: 20,
    padding: 4,
  },
  farmList: {
    padding: 12,
  },
  farmItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 16,
    marginBottom: 8,
  },
  farmItemActive: {
    backgroundColor: '#14532d',
    borderWidth: 1,
    borderColor: '#22c55e',
  },
  farmItemText: {
    color: '#f9fafb',
    fontSize: 15,
    fontWeight: '600',
    flex: 1,
  },
  farmItemTextActive: {
    color: '#86efac',
  },
  farmItemLocation: {
    color: '#6b7280',
    fontSize: 12,
    marginRight: 8,
  },
  checkmark: {
    color: '#22c55e',
    fontSize: 18,
    fontWeight: 'bold',
  },
});
