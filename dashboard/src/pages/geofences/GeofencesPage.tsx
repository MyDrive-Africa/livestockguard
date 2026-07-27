import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useAuthStore } from '@/stores/authStore';
import { apiClient } from '@/api/client';
import { PageTransition } from '@/components/motion';

interface Geofence {
  id: string;
  name: string;
  farm_id: string;
  fence_type: 'inclusion' | 'exclusion';
  active: boolean;
  alert_on_breach: boolean;
  geometry?: any;
  area_m2?: number;
  area_hectares?: number;
  area_km2?: number;
  created_at?: string;
}

export default function GeofencesPage() {
  const [geofences, setGeofences] = useState<Geofence[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Geofence | null>(null);
  const [editName, setEditName] = useState('');
  const [editType, setEditType] = useState('inclusion');
  const [editActive, setEditActive] = useState(true);
  const [editAlert, setEditAlert] = useState(true);
  const currentFarm = useAuthStore((state) => state.currentFarm);

  const fetchGeofences = useCallback(async () => {
    try {
      const params: Record<string, string> = {};
      if (currentFarm) params.farm_id = currentFarm;
      const resp = await apiClient.get('/api/geofences', { params });
      setGeofences(resp.data);
    } catch {
      // fallback
    } finally {
      setLoading(false);
    }
  }, [currentFarm]);

  useEffect(() => { fetchGeofences(); }, [fetchGeofences]);

  const openEdit = (fence: Geofence) => {
    setEditing(fence);
    setEditName(fence.name);
    setEditType(fence.fence_type);
    setEditActive(fence.active);
    setEditAlert(fence.alert_on_breach);
  };

  const saveEdit = async () => {
    if (!editing) return;
    try {
      await apiClient.patch(`/api/geofences/${editing.id}`, {
        name: editName,
        fence_type: editType,
        active: editActive,
        alert_on_breach: editAlert,
      });
      setEditing(null);
      fetchGeofences();
    } catch (err) {
      alert('Failed to save. Check console.');
      console.error(err);
    }
  };

  const deleteGeofence = async (id: string, name: string) => {
    if (!confirm(`Delete geofence "${name}"? This cannot be undone.`)) return;
    try {
      await apiClient.delete(`/api/geofences/${id}`);
      fetchGeofences();
    } catch (err) {
      alert('Failed to delete.');
      console.error(err);
    }
  };

  const toggleActive = async (fence: Geofence) => {
    try {
      await apiClient.patch(`/api/geofences/${fence.id}`, { active: !fence.active });
      fetchGeofences();
    } catch { /* ignore */ }
  };

  return (
    <PageTransition className="p-6 bg-gray-50 dark:bg-gray-900 min-h-full overflow-y-auto theme-transition">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Geofences</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {geofences.length} zones — {geofences.filter(f => f.active).length} active
          </p>
        </div>
        <a href="/map" className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors">
          + Draw on Map
        </a>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full"></div>
        </div>
      )}

      {!loading && geofences.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <p className="text-4xl mb-2">📍</p>
          <p>No geofences yet. Draw one on the map.</p>
        </div>
      )}

      {!loading && geofences.length > 0 && (
        <div className="grid gap-4">
          {geofences.map((fence, i) => (
            <motion.div
              key={fence.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.25 }}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 flex items-center justify-between theme-transition"
            >
              <div className="flex items-center gap-4">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-content ${
                  fence.fence_type === 'inclusion' ? 'bg-green-100 dark:bg-green-900/30' : 'bg-red-100 dark:bg-red-900/30'
                }`}>
                  <span className="text-lg ml-2">{fence.fence_type === 'inclusion' ? '🟢' : '🔴'}</span>
                </div>
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">{fence.name}</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {fence.fence_type} · {fence.alert_on_breach ? 'alerts on' : 'alerts off'}
                    {fence.area_hectares != null && fence.area_hectares >= 100 && ` · ${(fence.area_hectares / 100).toFixed(0)} km²`}
                    {fence.area_hectares != null && fence.area_hectares >= 1 && fence.area_hectares < 100 && ` · ${fence.area_hectares.toFixed(1)} ha`}
                    {fence.area_hectares != null && fence.area_hectares > 0 && fence.area_hectares < 1 && ` · ${Math.round(fence.area_hectares * 10000)} m²`}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {/* Active toggle */}
                <button
                  onClick={() => toggleActive(fence)}
                  className={`px-3 py-1 text-xs rounded-full font-medium ${
                    fence.active
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                      : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                  }`}
                >
                  {fence.active ? 'Active' : 'Inactive'}
                </button>

                {/* Edit */}
                <button
                  onClick={() => openEdit(fence)}
                  className="px-3 py-1 text-xs bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/50"
                >
                  Edit
                </button>

                {/* Edit on Map */}
                <a
                  href={`/map?editFence=${fence.id}`}
                  className="px-3 py-1 text-xs bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 rounded-lg hover:bg-purple-100 dark:hover:bg-purple-900/50"
                >
                  Redraw
                </a>

                {/* Delete */}
                <button
                  onClick={() => deleteGeofence(fence.id, fence.name)}
                  className="px-3 py-1 text-xs bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/50"
                >
                  Delete
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Edit Modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setEditing(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full mx-4 overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="bg-brand-600 text-white px-6 py-4">
              <h2 className="text-lg font-semibold">Edit Geofence</h2>
              <p className="text-brand-200 text-sm">{editing.id.slice(0, 8)}...</p>
            </div>
            <div className="p-6 space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </div>

              {/* Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
                <select
                  value={editType}
                  onChange={e => setEditType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                >
                  <option value="inclusion">Inclusion (cattle should stay inside)</option>
                  <option value="exclusion">Exclusion (cattle should stay out)</option>
                </select>
              </div>

              {/* Active */}
              <div className="flex items-center gap-3">
                <input type="checkbox" id="edit-active" checked={editActive} onChange={e => setEditActive(e.target.checked)} className="w-4 h-4" />
                <label htmlFor="edit-active" className="text-sm text-gray-700 dark:text-gray-300">Active (monitoring enabled)</label>
              </div>

              {/* Alert on breach */}
              <div className="flex items-center gap-3">
                <input type="checkbox" id="edit-alert" checked={editAlert} onChange={e => setEditAlert(e.target.checked)} className="w-4 h-4" />
                <label htmlFor="edit-alert" className="text-sm text-gray-700 dark:text-gray-300">Alert on breach</label>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setEditing(null)} className="px-4 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg">Cancel</button>
                <button onClick={saveEdit} className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700">Save Changes</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageTransition>
  );
}
