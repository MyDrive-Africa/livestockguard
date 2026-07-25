import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useAuthStore } from '@/stores/authStore';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { apiClient } from '@/api/client';
import { PageTransition } from '@/components/motion';
import type { Animal } from '@/types';

function BatteryBadge({ level }: { level: number | null | undefined }) {
  if (level == null) return <span className="text-xs text-gray-400">—</span>;
  const color =
    level > 70
      ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
      : level > 30
        ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300'
        : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300';
  return (
    <span className={`px-2 py-0.5 text-xs rounded-full ${color}`}>
      {level}%
    </span>
  );
}

function StatusIndicator({ hasPosition, battery }: { hasPosition: boolean; battery: number | null | undefined }) {
  if (!hasPosition) return <span className="flex items-center gap-1 text-xs text-gray-400"><span className="w-2 h-2 rounded-full bg-gray-300"></span>No signal</span>;
  if (battery != null && battery < 20) return <span className="flex items-center gap-1 text-xs text-orange-600"><span className="w-2 h-2 rounded-full bg-orange-400"></span>Low battery</span>;
  return <span className="flex items-center gap-1 text-xs text-green-600"><span className="w-2 h-2 rounded-full bg-green-400"></span>Active</span>;
}

export default function AnimalsPage() {
  const [animals, setAnimals] = useState<Animal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [selectedAnimal, setSelectedAnimal] = useState<Animal | null>(null);

  const currentFarm = useAuthStore((state) => state.currentFarm);
  const positions = useRealtimeStore((state) => state.positions);

  const fetchAnimals = useCallback(async () => {
    try {
      setError(null);
      const params: Record<string, string> = {};
      if (currentFarm) params.farm_id = currentFarm;

      const resp = await apiClient.get('/api/animals', { params });
      setAnimals(resp.data);
    } catch (err: any) {
      setError('Failed to load animals');
      console.error('Animals fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [currentFarm]);

  useEffect(() => {
    fetchAnimals();
  }, [fetchAnimals]);

  // Update animals with real-time position data from WebSocket
  useEffect(() => {
    if (positions.size === 0) return;
    setAnimals((prev) =>
      prev.map((animal) => {
        const pos = positions.get(animal.id);
        if (!pos) return animal;
        return {
          ...animal,
          last_latitude: pos.position.latitude,
          last_longitude: pos.position.longitude,
          last_speed: pos.position.speed,
          battery_level: pos.batteryLevel ?? animal.battery_level,
        };
      })
    );
  }, [positions]);

  // Filter by search
  const filteredAnimals = animals.filter(
    (a) =>
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.tag_id.toLowerCase().includes(search.toLowerCase()) ||
      (a.breed && a.breed.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <PageTransition className="p-6 h-full overflow-y-auto bg-gray-50 dark:bg-gray-900 theme-transition">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Animals</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {animals.length} registered{' '}
            {animals.filter((a) => a.last_latitude).length} with GPS
          </p>
        </div>
        <button className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors">
          + Add Animal
        </button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search by name, tag, or breed..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-md px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
        />
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full"></div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p className="text-red-700">{error}</p>
          <button onClick={fetchAnimals} className="text-sm text-red-600 underline mt-1">
            Retry
          </button>
        </div>
      )}

      {/* Table */}
      {!loading && !error && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden theme-transition">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Name</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Tag ID</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Breed</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Last Position</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Speed</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Battery</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {filteredAnimals.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                    {search ? 'No animals match your search' : 'No animals registered yet'}
                  </td>
                </tr>
              )}
              {filteredAnimals.map((animal, i) => (
                <motion.tr
                  key={animal.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04, duration: 0.25 }}
                  onClick={() => setSelectedAnimal(animal)}
                  className="hover:bg-gray-50 dark:hover:bg-gray-750 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🐄</span>
                      <span className="font-medium text-gray-900 dark:text-white">{animal.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400 font-mono text-sm">{animal.tag_id}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{animal.breed || '—'}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400 text-sm font-mono">
                    {animal.last_latitude != null
                      ? `${animal.last_latitude.toFixed(5)}, ${animal.last_longitude!.toFixed(5)}`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400 text-sm">
                    {animal.last_speed != null ? `${animal.last_speed.toFixed(1)} km/h` : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <BatteryBadge level={animal.battery_level} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusIndicator
                      hasPosition={animal.last_latitude != null}
                      battery={animal.battery_level}
                    />
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail Modal */}
      {selectedAnimal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setSelectedAnimal(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full mx-4 overflow-hidden theme-transition"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="bg-brand-600 text-white px-6 py-4">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                🐄 {selectedAnimal.name}
              </h2>
              <p className="text-brand-200 text-sm">{selectedAnimal.tag_id}</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Species</p>
                  <p className="font-medium text-gray-900 dark:text-white">{selectedAnimal.species}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Breed</p>
                  <p className="font-medium text-gray-900 dark:text-white">{selectedAnimal.breed || '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Device</p>
                  <p className="font-medium text-gray-900 dark:text-white font-mono text-sm">
                    {selectedAnimal.device_serial || 'Unassigned'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Battery</p>
                  <BatteryBadge level={selectedAnimal.battery_level} />
                </div>
              </div>

              {selectedAnimal.last_latitude != null && (
                <div className="border-t dark:border-gray-700 pt-4">
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                    Last Known Position
                  </p>
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 font-mono text-sm text-gray-900 dark:text-gray-100">
                    <p>Lat: {selectedAnimal.last_latitude.toFixed(6)}</p>
                    <p>Lon: {selectedAnimal.last_longitude!.toFixed(6)}</p>
                    {selectedAnimal.last_speed != null && (
                      <p>Speed: {selectedAnimal.last_speed.toFixed(1)} km/h</p>
                    )}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 border-t dark:border-gray-700 pt-4">
                <a
                  href={`/map`}
                  className="px-4 py-2 text-sm bg-brand-100 text-brand-700 rounded-lg hover:bg-brand-200"
                >
                  View on Map
                </a>
                <button
                  onClick={() => setSelectedAnimal(null)}
                  className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageTransition>
  );
}
