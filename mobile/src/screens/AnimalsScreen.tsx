import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl } from 'react-native';
import { api } from '../services/api';
import { useFarm } from '../context/FarmContext';

interface Animal {
  id: string;
  name: string;
  tag_id: string;
  breed?: string;
  gender?: string;
  colour?: string;
  status: string;
}

export default function AnimalsScreen() {
  const { selectedFarm } = useFarm();
  const [animals, setAnimals] = useState<Animal[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAnimals = async () => {
    if (!selectedFarm) return;
    try {
      const resp = await api.get(`/api/animals?farm_id=${selectedFarm.id}`);
      setAnimals(resp.data);
    } catch (err) {
      console.warn('Failed to fetch animals:', err);
    }
  };

  useEffect(() => { fetchAnimals(); }, [selectedFarm]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchAnimals();
    setRefreshing(false);
  };

  const renderAnimal = ({ item }: { item: Animal }) => (
    <View style={styles.card}>
      <View style={styles.row}>
        <Text style={styles.name}>🐄 {item.name}</Text>
        <Text style={styles.gender}>{item.gender === 'male' ? '♂' : item.gender === 'female' ? '♀' : ''}</Text>
      </View>
      <Text style={styles.detail}>{item.tag_id} · {item.breed || '—'} · {item.colour || '—'}</Text>
    </View>
  );

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Animals ({animals.length})</Text>
      <FlatList
        data={animals}
        keyExtractor={(item) => item.id}
        renderItem={renderAnimal}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" />}
        contentContainerStyle={{ paddingBottom: 40 }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827', padding: 16, paddingTop: 60 },
  title: { fontSize: 20, fontWeight: 'bold', color: '#fff', marginBottom: 16 },
  card: { backgroundColor: '#1f2937', borderRadius: 10, padding: 14, marginBottom: 8 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  name: { fontSize: 15, fontWeight: '600', color: '#fff' },
  gender: { fontSize: 16, color: '#9ca3af' },
  detail: { fontSize: 12, color: '#6b7280', marginTop: 4 },
});
