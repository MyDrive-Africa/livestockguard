import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useAuthStore } from '@/stores/authStore';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { apiClient } from '@/api/client';
import { PageTransition } from '@/components/motion';
import type { Animal } from '@/types';

// ─── Sub-components ──────────────────────────────────────────────────────────

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

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
    sold: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
    deceased: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
    transferred: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
  };
  return (
    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${styles[status] || styles.active}`}>
      {status}
    </span>
  );
}

function GenderIcon({ gender }: { gender?: string }) {
  if (gender === 'male') return <span className="text-blue-500" title="Male">♂</span>;
  if (gender === 'female') return <span className="text-pink-500" title="Female">♀</span>;
  return <span className="text-gray-400">—</span>;
}

function AnimalAvatar({ animal }: { animal: Animal }) {
  if (animal.photo_url) {
    return (
      <img
        src={animal.photo_url}
        alt={animal.name}
        className="w-8 h-8 rounded-full object-cover border border-gray-200 dark:border-gray-600"
      />
    );
  }
  return <span className="text-lg">🐄</span>;
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function AnimalsPage() {
  const [animals, setAnimals] = useState<Animal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('active');
  const [genderFilter, setGenderFilter] = useState<string>('');
  const [selectedAnimal, setSelectedAnimal] = useState<Animal | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState({
    name: '', tag_id: '', breed: '', gender: '', colour: '',
    description: '', weight_kg: '', date_of_birth: '', photo_url: '',
    device_type: 'eartag', ble_mac: '',
  });
  const [addSubmitting, setAddSubmitting] = useState(false);

  const currentFarm = useAuthStore((state) => state.currentFarm);
  const positions = useRealtimeStore((state) => state.positions);

  const fetchAnimals = useCallback(async () => {
    try {
      setError(null);
      const params: Record<string, string> = {};
      if (currentFarm) params.farm_id = currentFarm;
      if (statusFilter) params.status = statusFilter;
      if (genderFilter) params.gender = genderFilter;

      const resp = await apiClient.get('/api/animals', { params });
      setAnimals(resp.data);
    } catch (err: any) {
      setError('Failed to load animals');
      console.error('Animals fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [currentFarm, statusFilter, genderFilter]);

  useEffect(() => {
    fetchAnimals();
  }, [fetchAnimals]);

  const handleAddAnimal = async () => {
    if (!addForm.name || !addForm.tag_id) return;
    setAddSubmitting(true);
    try {
      const farmId = currentFarm || 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
      const resp = await apiClient.post('/api/animals', {
        name: addForm.name,
        tag_id: addForm.tag_id,
        species: 'cattle',
        breed: addForm.breed || undefined,
        gender: addForm.gender || undefined,
        colour: addForm.colour || undefined,
        description: addForm.description || undefined,
        weight_kg: addForm.weight_kg ? parseFloat(addForm.weight_kg) : undefined,
        date_of_birth: addForm.date_of_birth || undefined,
        photo_url: addForm.photo_url || undefined,
        farm_id: farmId,
      });

      // If BLE MAC provided, register the ear tag and link to the new animal
      const newAnimalId = resp.data?.id;
      if (addForm.ble_mac && newAnimalId) {
        try {
          await apiClient.post('/api/gateway/tags', {
            farm_id: farmId,
            animal_id: newAnimalId,
            mac_address: addForm.ble_mac.toUpperCase(),
            tag_name: `Tag-${addForm.name}`,
          });
        } catch (tagErr) {
          console.warn('BLE tag registration failed (may already exist):', tagErr);
        }
      }

      setShowAddForm(false);
      setAddForm({ name: '', tag_id: '', breed: '', gender: '', colour: '', description: '', weight_kg: '', date_of_birth: '', photo_url: '', device_type: 'eartag', ble_mac: '' });
      fetchAnimals();
    } catch (err) {
      alert('Failed to add animal. Check console.');
      console.error(err);
    } finally {
      setAddSubmitting(false);
    }
  };

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
      (a.breed && a.breed.toLowerCase().includes(search.toLowerCase())) ||
      (a.colour && a.colour.toLowerCase().includes(search.toLowerCase())) ||
      (a.description && a.description.toLowerCase().includes(search.toLowerCase()))
  );

  // Summary counts
  const maleCount = animals.filter((a) => a.gender === 'male').length;
  const femaleCount = animals.filter((a) => a.gender === 'female').length;
  const withGps = animals.filter((a) => a.last_latitude != null).length;

  return (
    <PageTransition className="p-6 h-full overflow-y-auto bg-gray-50 dark:bg-gray-900 theme-transition">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Animals</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {animals.length} registered — {maleCount} ♂ / {femaleCount} ♀ — {withGps} with GPS
          </p>
        </div>
        <button onClick={() => setShowAddForm(true)} className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors">
          + Add Animal
        </button>
      </div>

      {/* Filters Row */}
      <div className="flex flex-wrap gap-3 mb-4">
        {/* Search */}
        <input
          type="text"
          placeholder="Search name, tag, breed, colour..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] max-w-md px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
        />
        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm"
          aria-label="Filter by status"
        >
          <option value="active">Active</option>
          <option value="">All Status</option>
          <option value="sold">Sold</option>
          <option value="deceased">Deceased</option>
          <option value="transferred">Transferred</option>
        </select>
        {/* Gender filter */}
        <select
          value={genderFilter}
          onChange={(e) => setGenderFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm"
          aria-label="Filter by gender"
        >
          <option value="">All Gender</option>
          <option value="male">Male ♂</option>
          <option value="female">Female ♀</option>
        </select>
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
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                <tr>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Animal</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Tag ID</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Breed</th>
                  <th className="text-center px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Gender</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Colour</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Weight</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Status</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Battery</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Position</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {filteredAnimals.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                      {search ? 'No animals match your search' : 'No animals registered yet'}
                    </td>
                  </tr>
                )}
                {filteredAnimals.map((animal, i) => (
                  <motion.tr
                    key={animal.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03, duration: 0.2 }}
                    onClick={() => setSelectedAnimal(animal)}
                    className="hover:bg-gray-50 dark:hover:bg-gray-750 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <AnimalAvatar animal={animal} />
                        <span className="font-medium text-gray-900 dark:text-white">{animal.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 font-mono text-sm">{animal.tag_id}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{animal.breed || '—'}</td>
                    <td className="px-4 py-3 text-center">
                      <GenderIcon gender={animal.gender} />
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 text-sm">{animal.colour || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 text-sm">
                      {animal.weight_kg ? `${animal.weight_kg} kg` : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={animal.status} />
                    </td>
                    <td className="px-4 py-3">
                      <BatteryBadge level={animal.battery_level} />
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 text-sm font-mono">
                      {animal.last_latitude != null
                        ? `${animal.last_latitude.toFixed(5)}, ${animal.last_longitude!.toFixed(5)}`
                        : '—'}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selectedAnimal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setSelectedAnimal(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full mx-4 overflow-hidden theme-transition max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="bg-brand-600 text-white px-6 py-4">
              <div className="flex items-center gap-3">
                {selectedAnimal.photo_url ? (
                  <img src={selectedAnimal.photo_url} alt={selectedAnimal.name}
                    className="w-12 h-12 rounded-full object-cover border-2 border-white/30" />
                ) : (
                  <span className="text-3xl">🐄</span>
                )}
                <div>
                  <h2 className="text-lg font-semibold flex items-center gap-2">
                    {selectedAnimal.name}
                    <GenderIcon gender={selectedAnimal.gender} />
                  </h2>
                  <p className="text-brand-200 text-sm">{selectedAnimal.tag_id}</p>
                </div>
              </div>
            </div>

            {/* Body */}
            <div className="p-6 space-y-4">
              {/* Description */}
              {selectedAnimal.description && (
                <p className="text-sm text-gray-600 dark:text-gray-400 italic">
                  {selectedAnimal.description}
                </p>
              )}

              {/* Details grid */}
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
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Gender</p>
                  <p className="font-medium text-gray-900 dark:text-white">
                    {selectedAnimal.gender === 'male' ? 'Male ♂' : selectedAnimal.gender === 'female' ? 'Female ♀' : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Colour</p>
                  <p className="font-medium text-gray-900 dark:text-white">{selectedAnimal.colour || '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Weight</p>
                  <p className="font-medium text-gray-900 dark:text-white">
                    {selectedAnimal.weight_kg ? `${selectedAnimal.weight_kg} kg` : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Date of Birth</p>
                  <p className="font-medium text-gray-900 dark:text-white">{selectedAnimal.date_of_birth || '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Status</p>
                  <StatusBadge status={selectedAnimal.status} />
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Device</p>
                  <p className="font-medium text-gray-900 dark:text-white font-mono text-sm">
                    {selectedAnimal.device_serial || 'Not assigned'}
                  </p>
                </div>
              </div>

              {/* Position */}
              {selectedAnimal.last_latitude != null && (
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Last Known Position</p>
                  <p className="font-mono text-sm text-gray-900 dark:text-white">
                    {selectedAnimal.last_latitude.toFixed(6)}, {selectedAnimal.last_longitude!.toFixed(6)}
                  </p>
                  {selectedAnimal.last_speed != null && (
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Speed: {selectedAnimal.last_speed.toFixed(1)} km/h
                    </p>
                  )}
                </div>
              )}

              {/* Close button */}
              <div className="flex justify-end pt-2">
                <button
                  onClick={() => setSelectedAnimal(null)}
                  className="px-4 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Add Animal Modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAddForm(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="bg-brand-600 text-white px-6 py-4">
              <h2 className="text-lg font-semibold">Add New Animal</h2>
              <p className="text-brand-200 text-sm">Register a cow to the current farm</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name *</label>
                  <input type="text" value={addForm.name} onChange={e => setAddForm(f => ({...f, name: e.target.value}))} placeholder="e.g. Bella" className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Tag ID *</label>
                  <input type="text" value={addForm.tag_id} onChange={e => setAddForm(f => ({...f, tag_id: e.target.value}))} placeholder="e.g. LV-2025-051" className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Breed</label>
                  <select value={addForm.breed} onChange={e => setAddForm(f => ({...f, breed: e.target.value}))} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                    <option value="">Select breed</option>
                    <option value="Nguni">Nguni</option>
                    <option value="Brahman">Brahman</option>
                    <option value="Bonsmara">Bonsmara</option>
                    <option value="Hereford">Hereford</option>
                    <option value="Angus">Angus</option>
                    <option value="Jersey">Jersey</option>
                    <option value="Holstein">Holstein</option>
                    <option value="Afrikaner">Afrikaner</option>
                    <option value="Drakensberger">Drakensberger</option>
                    <option value="Mixed">Mixed</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Gender</label>
                  <select value={addForm.gender} onChange={e => setAddForm(f => ({...f, gender: e.target.value}))} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                    <option value="">Select gender</option>
                    <option value="female">Female (Cow)</option>
                    <option value="male">Male (Bull)</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Colour</label>
                  <input type="text" value={addForm.colour} onChange={e => setAddForm(f => ({...f, colour: e.target.value}))} placeholder="e.g. Brown and white" className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Weight (kg)</label>
                  <input type="number" value={addForm.weight_kg} onChange={e => setAddForm(f => ({...f, weight_kg: e.target.value}))} placeholder="e.g. 420" className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Date of Birth</label>
                  <input type="date" value={addForm.date_of_birth} onChange={e => setAddForm(f => ({...f, date_of_birth: e.target.value}))} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Photo URL</label>
                  <input type="text" value={addForm.photo_url} onChange={e => setAddForm(f => ({...f, photo_url: e.target.value}))} placeholder="https://..." className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
                <textarea value={addForm.description} onChange={e => setAddForm(f => ({...f, description: e.target.value}))} placeholder="Physical description, markings, temperament..." rows={2} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </div>

              {/* Tracking Device */}
              <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Tracking Device</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Device Type</label>
                    <select value={addForm.device_type} onChange={e => setAddForm(f => ({...f, device_type: e.target.value}))} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                      <option value="eartag">BLE Ear Tag</option>
                      <option value="collar">GPS Collar</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      {addForm.device_type === 'eartag' ? 'BLE MAC Address' : 'Collar Serial'}
                    </label>
                    <input type="text" value={addForm.ble_mac} onChange={e => setAddForm(f => ({...f, ble_mac: e.target.value}))} placeholder={addForm.device_type === 'eartag' ? 'AA:BB:CC:DD:EE:FF' : 'LG-XXX'} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                  </div>
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  {addForm.device_type === 'eartag'
                    ? 'The BLE MAC is printed on the ear tag or detected by the gateway scanner.'
                    : 'The collar serial is on the device label.'}
                </p>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setShowAddForm(false)} className="px-4 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg">Cancel</button>
                <button onClick={handleAddAnimal} disabled={!addForm.name || !addForm.tag_id || addSubmitting} className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">
                  {addSubmitting ? 'Adding...' : 'Add Animal'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageTransition>
  );
}
