import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useAuthStore } from '@/stores/authStore';
import { apiClient } from '@/api/client';
import { PageTransition, AnimatedCard } from '@/components/motion';

// ─── Types ───────────────────────────────────────────────────────────────────

interface Gateway {
  id: string;
  farm_id: string;
  serial_number: string;
  name: string;
  device_type: string;
  herdsman_name?: string;
  herdsman_phone?: string;
  status: string;
  last_seen?: string;
  last_latitude?: number;
  last_longitude?: number;
  last_battery_pct?: number;
  ble_scan_interval_ms: number;
  report_interval_sec: number;
  max_ble_range_m: number;
  animals_in_range?: number;
}

interface AnimalSighting {
  animal_id: string;
  animal_name: string;
  tag_id: string;
  mac_address: string;
  last_seen: string;
  rssi: number;
  estimated_distance_m?: number;
  latitude: number;
  longitude: number;
}

interface GatewayStatus {
  gateway: Gateway;
  active_session?: {
    id: string;
    started_at: string;
    herdsman_name?: string;
    animals_seen: number;
    total_sightings: number;
  };
  recent_animals: AnimalSighting[];
  total_sightings_today: number;
  unique_animals_today: number;
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-green-400',
    inactive: 'bg-gray-400',
    maintenance: 'bg-yellow-400',
    lost: 'bg-red-400',
  };
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${colors[status] || colors.inactive}`} />;
}

function SignalBars({ rssi }: { rssi: number }) {
  const strength = rssi > -60 ? 3 : rssi > -75 ? 2 : 1;
  return (
    <span className="inline-flex gap-0.5 items-end h-4" title={`${rssi} dBm`}>
      {[1, 2, 3].map((bar) => (
        <span
          key={bar}
          className={`w-1 rounded-sm ${bar <= strength ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'}`}
          style={{ height: `${bar * 5 + 3}px` }}
        />
      ))}
    </span>
  );
}

function TimeAgo({ iso }: { iso?: string }) {
  if (!iso) return <span className="text-gray-400 text-xs">Never</span>;
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return <span className="text-green-600 text-xs">Just now</span>;
  if (mins < 60) return <span className="text-xs text-gray-600 dark:text-gray-400">{mins}m ago</span>;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return <span className="text-xs text-orange-600">{hrs}h ago</span>;
  return <span className="text-xs text-red-600">{Math.floor(hrs / 24)}d ago</span>;
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function GatewayPage() {
  const [gateways, setGateways] = useState<Gateway[]>([]);
  const [selectedGateway, setSelectedGateway] = useState<GatewayStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingGateway, setEditingGateway] = useState<Gateway | null>(null);
  const [editForm, setEditForm] = useState({ name: '', herdsman_name: '', herdsman_phone: '' });
  const [simulatorRunning, setSimulatorRunning] = useState(false);

  const currentFarm = useAuthStore((state) => state.currentFarm);

  // Herd count / missing animals
  interface HerdCount {
    total_registered: number;
    seen_today: number;
    seen_this_session: number;
    missing_count: number;
    coverage_pct: number;
    missing: { animal_id: string; name: string; tag_id: string; breed?: string; gender?: string; colour?: string; last_seen?: string; last_seen_by?: string; hours_missing?: number }[];
  }
  const [herdCount, setHerdCount] = useState<HerdCount | null>(null);

  const fetchGateways = useCallback(async () => {
    try {
      setError(null);
      const params: Record<string, string> = {};
      if (currentFarm) params.farm_id = currentFarm;
      const resp = await apiClient.get('/api/gateway', { params });
      setGateways(resp.data);
    } catch (err: any) {
      setError('Failed to load gateways');
    } finally {
      setLoading(false);
    }
  }, [currentFarm]);

  useEffect(() => {
    fetchGateways();
  }, [fetchGateways]);

  // Poll simulator status and auto-refresh data when running
  useEffect(() => {
    let cancelled = false;

    async function pollSimulatorStatus() {
      try {
        const resp = await fetch('/dev/simulator/status');
        if (!resp.ok) return;
        const data = await resp.json();
        if (!cancelled) {
          setSimulatorRunning(data.running);
        }
      } catch {
        // Dev endpoint not available (production) — ignore
      }
    }

    pollSimulatorStatus();
    const statusInterval = setInterval(pollSimulatorStatus, 5000);

    return () => {
      cancelled = true;
      clearInterval(statusInterval);
    };
  }, []);

  // Auto-refresh gateway + herd data when simulator is running
  useEffect(() => {
    if (!simulatorRunning) return;

    const refreshInterval = setInterval(() => {
      fetchGateways();
    }, 15000);

    return () => clearInterval(refreshInterval);
  }, [simulatorRunning, fetchGateways]);

  // Fetch herd count for current farm (and refresh periodically when sim running)
  useEffect(() => {
    async function loadHerdCount() {
      const farmId = currentFarm || 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
      try {
        const resp = await apiClient.get(`/api/gateway/herd-count/${farmId}`);
        setHerdCount(resp.data);
      } catch {
        // Herd count unavailable (no BLE tags registered yet)
      }
    }
    loadHerdCount();

    if (simulatorRunning) {
      const herdInterval = setInterval(loadHerdCount, 15000);
      return () => clearInterval(herdInterval);
    }
  }, [currentFarm, simulatorRunning]);

  const fetchGatewayStatus = async (serial: string) => {
    try {
      const resp = await apiClient.get(`/api/gateway/status/${serial}`);
      setSelectedGateway(resp.data);
    } catch {
      // Gateway status unavailable
    }
  };

  const openEditGateway = (gw: Gateway, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingGateway(gw);
    setEditForm({ name: gw.name, herdsman_name: gw.herdsman_name || '', herdsman_phone: gw.herdsman_phone || '' });
  };

  const saveGatewayEdit = async () => {
    if (!editingGateway) return;
    try {
      await apiClient.patch(`/api/gateway/${editingGateway.id}`, {
        name: editForm.name,
        herdsman_name: editForm.herdsman_name,
        herdsman_phone: editForm.herdsman_phone,
      });
      setEditingGateway(null);
      fetchGateways();
    } catch (err) {
      alert('Failed to update. Check console.');
      console.error(err);
    }
  };

  // Summary stats
  const activeCount = gateways.filter((g) => g.status === 'active').length;
  const onlineCount = gateways.filter((g) => {
    if (!g.last_seen) return false;
    return Date.now() - new Date(g.last_seen).getTime() < 300000; // 5 min
  }).length;

  return (
    <PageTransition className="p-6 h-full overflow-y-auto bg-gray-50 dark:bg-gray-900 theme-transition">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Herdsman Gateways</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            BLE ear tag collection via herdsman-carried devices
          </p>
        </div>
        <button className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors">
          + Register Gateway
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <AnimatedCard delay={0} className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{gateways.length}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400">Total Gateways</p>
        </AnimatedCard>
        <AnimatedCard delay={0.1} className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-2xl font-bold text-green-600">{onlineCount}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400">Online Now</p>
        </AnimatedCard>
        <AnimatedCard delay={0.2} className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-2xl font-bold text-blue-600">{activeCount}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400">Active</p>
        </AnimatedCard>
        <AnimatedCard delay={0.3} className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 text-center">
          <p className="text-2xl font-bold text-purple-600">
            {gateways.reduce((sum, g) => sum + (g.animals_in_range || 0), 0)}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400">Animals in Range</p>
        </AnimatedCard>
      </div>

      {/* Simulator Status Card */}
      <AnimatedCard delay={0.4} className="mb-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">🔄</span>
            <div>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">Simulator</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {simulatorRunning ? 'Data flowing — simulator active' : 'No recent data — simulator stopped'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${simulatorRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            <button
              onClick={async () => {
                try {
                  const endpoint = simulatorRunning ? '/dev/simulator/stop' : '/dev/simulator/start';
                  const resp = await fetch(endpoint, { method: 'POST' });
                  const data = await resp.json();
                  if (data.status === 'started') {
                    setSimulatorRunning(true);
                  } else if (data.status === 'stopped') {
                    setSimulatorRunning(false);
                  } else if (data.status === 'already_running') {
                    setSimulatorRunning(true);
                  }
                } catch {
                  // Fallback: copy command if dev endpoint not available
                  navigator.clipboard.writeText('make simulate-loop');
                  alert('Dev control not available.\nCopied: make simulate-loop\nRun in terminal.');
                }
              }}
              className="px-3 py-1.5 text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              title={simulatorRunning ? 'Stop simulators' : 'Start simulators in loop mode'}
            >
              {simulatorRunning ? '⏹ Stop' : '▶ Start Loop'}
            </button>
          </div>
        </div>
      </AnimatedCard>

      {/* Cattle Count / Herd Reconciliation */}
      {herdCount && (
        <div className="mb-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Cattle Count</h3>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                herdCount.coverage_pct >= 100 ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300' :
                herdCount.coverage_pct >= 80 ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300' :
                'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
              }`}>
                {herdCount.coverage_pct}% coverage
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900 dark:text-white">{herdCount.total_registered}</p>
                <p className="text-xs text-gray-500">Total Tagged</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-green-600">{herdCount.seen_today}</p>
                <p className="text-xs text-gray-500">Seen Today</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-600">{herdCount.seen_this_session}</p>
                <p className="text-xs text-gray-500">This Session</p>
              </div>
              <div className="text-center">
                <p className={`text-2xl font-bold ${herdCount.missing_count > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {herdCount.missing_count}
                </p>
                <p className="text-xs text-gray-500">Missing</p>
              </div>
            </div>

            {/* Missing Animals Alert */}
            {herdCount.missing_count > 0 && (
              <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-red-500 text-lg">⚠️</span>
                  <h4 className="text-sm font-semibold text-red-700 dark:text-red-400">
                    {herdCount.missing_count} Animal{herdCount.missing_count > 1 ? 's' : ''} Not Seen (24h+)
                  </h4>
                </div>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {herdCount.missing.map((animal) => (
                    <div key={animal.animal_id} className="flex items-center justify-between py-2 px-3 bg-red-50 dark:bg-red-900/10 rounded-lg border border-red-100 dark:border-red-800">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">🐄</span>
                        <div>
                          <p className="font-medium text-gray-900 dark:text-white text-sm">{animal.name}</p>
                          <p className="text-xs text-gray-500">
                            {animal.tag_id} · {animal.breed || '—'} · {animal.gender === 'male' ? '♂' : animal.gender === 'female' ? '♀' : ''}
                            {animal.colour ? ` · ${animal.colour}` : ''}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        {animal.hours_missing != null ? (
                          <p className="text-xs text-red-600 font-medium">{animal.hours_missing}h missing</p>
                        ) : (
                          <p className="text-xs text-gray-400">Never detected</p>
                        )}
                        {animal.last_seen_by && (
                          <p className="text-xs text-gray-400">Last: {animal.last_seen_by}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {herdCount.missing_count === 0 && herdCount.total_registered > 0 && (
              <div className="border-t border-gray-200 dark:border-gray-700 pt-3 text-center">
                <p className="text-sm text-green-600 dark:text-green-400 font-medium">
                  ✓ All {herdCount.total_registered} cattle accounted for today
                </p>
              </div>
            )}
          </div>
        </div>
      )}

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
          <button onClick={fetchGateways} className="text-sm text-red-600 underline mt-1">Retry</button>
        </div>
      )}

      {/* Gateway Cards */}
      {!loading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {gateways.length === 0 && (
            <div className="col-span-full text-center py-12 text-gray-500 dark:text-gray-400">
              <p className="text-4xl mb-2">📶</p>
              <p>No gateways registered yet</p>
              <p className="text-sm mt-1">Register a herdsman's phone or dedicated BLE gateway device</p>
            </div>
          )}
          {gateways.map((gw, i) => (
            <motion.div
              key={gw.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.25 }}
              onClick={() => fetchGatewayStatus(gw.serial_number)}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 cursor-pointer hover:border-brand-400 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <StatusDot status={gw.status} />
                  <h3 className="font-semibold text-gray-900 dark:text-white">{gw.name}</h3>
                </div>
                <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-gray-600 dark:text-gray-400">
                  {gw.device_type === 'phone' ? '📱' : '🔌'} {gw.device_type}
                </span>
              </div>

              <div className="space-y-1.5 text-sm">
                {gw.herdsman_name && (
                  <p className="text-gray-600 dark:text-gray-400">
                    👤 {gw.herdsman_name}
                  </p>
                )}
                <button
                  onClick={(e) => openEditGateway(gw, e)}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                  ✏️ Edit herdsman
                </button>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Last seen:</span>
                  <TimeAgo iso={gw.last_seen} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Battery:</span>
                  <span className={`text-sm font-medium ${
                    (gw.last_battery_pct ?? 100) > 50 ? 'text-green-600' :
                    (gw.last_battery_pct ?? 100) > 20 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {gw.last_battery_pct != null ? `${gw.last_battery_pct}%` : '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Serial:</span>
                  <span className="font-mono text-xs text-gray-600 dark:text-gray-400">{gw.serial_number}</span>
                </div>
              </div>

              {gw.last_latitude && (
                <p className="mt-2 text-xs font-mono text-gray-400">
                  📍 {gw.last_latitude.toFixed(5)}, {gw.last_longitude?.toFixed(5)}
                </p>
              )}
            </motion.div>
          ))}
        </div>
      )}

      {/* Selected Gateway Detail Panel */}
      {selectedGateway && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setSelectedGateway(null)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-2xl w-full mx-4 overflow-hidden max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="bg-brand-600 text-white px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">{selectedGateway.gateway.name}</h2>
                  <p className="text-brand-200 text-sm">
                    {selectedGateway.gateway.herdsman_name || 'No herdsman assigned'}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold">{selectedGateway.unique_animals_today}</p>
                  <p className="text-brand-200 text-xs">animals today</p>
                </div>
              </div>
            </div>

            {/* Session info */}
            {selectedGateway.active_session && (
              <div className="px-6 py-3 bg-green-50 dark:bg-green-900/20 border-b border-green-100 dark:border-green-800">
                <p className="text-sm text-green-800 dark:text-green-300 font-medium">
                  Active patrol since {new Date(selectedGateway.active_session.started_at).toLocaleTimeString()}
                </p>
                <p className="text-xs text-green-600 dark:text-green-400">
                  {selectedGateway.active_session.animals_seen} animals seen, {selectedGateway.active_session.total_sightings} total pings
                </p>
              </div>
            )}

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-4 px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <div className="text-center">
                <p className="text-xl font-bold text-gray-900 dark:text-white">{selectedGateway.total_sightings_today}</p>
                <p className="text-xs text-gray-500">Sightings today</p>
              </div>
              <div className="text-center">
                <p className="text-xl font-bold text-gray-900 dark:text-white">{selectedGateway.unique_animals_today}</p>
                <p className="text-xs text-gray-500">Unique animals</p>
              </div>
              <div className="text-center">
                <p className="text-xl font-bold text-gray-900 dark:text-white">{selectedGateway.recent_animals.length}</p>
                <p className="text-xs text-gray-500">In range now</p>
              </div>
            </div>

            {/* Recent animals list */}
            <div className="px-6 py-4">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                Recent Animal Sightings (last hour)
              </h3>
              {selectedGateway.recent_animals.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No animals detected recently</p>
              ) : (
                <div className="space-y-2">
                  {selectedGateway.recent_animals.map((animal) => (
                    <div key={animal.animal_id} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700 last:border-0">
                      <div className="flex items-center gap-3">
                        <span className="text-lg">🐄</span>
                        <div>
                          <p className="font-medium text-gray-900 dark:text-white text-sm">{animal.animal_name}</p>
                          <p className="text-xs text-gray-500 font-mono">{animal.tag_id}</p>
                        </div>
                      </div>
                      <div className="text-right flex items-center gap-3">
                        <SignalBars rssi={animal.rssi} />
                        <div>
                          <p className="text-xs text-gray-600 dark:text-gray-400">
                            {animal.estimated_distance_m != null ? `~${animal.estimated_distance_m}m` : '—'}
                          </p>
                          <TimeAgo iso={animal.last_seen} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Close */}
            <div className="px-6 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                onClick={() => setSelectedGateway(null)}
                className="px-4 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Edit Herdsman Modal */}
      {editingGateway && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setEditingGateway(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="bg-brand-600 text-white px-6 py-4">
              <h2 className="text-lg font-semibold">Edit Herdsman / Gateway</h2>
              <p className="text-brand-200 text-sm">{editingGateway.serial_number}</p>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Gateway Name</label>
                <input type="text" value={editForm.name} onChange={e => setEditForm(f => ({...f, name: e.target.value}))} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Herdsman Name</label>
                <input type="text" value={editForm.herdsman_name} onChange={e => setEditForm(f => ({...f, herdsman_name: e.target.value}))} placeholder="e.g. Teboho Mpeki" className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Herdsman Phone</label>
                <input type="tel" value={editForm.herdsman_phone} onChange={e => setEditForm(f => ({...f, herdsman_phone: e.target.value}))} placeholder="+27 82 XXX XXXX" className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setEditingGateway(null)} className="px-4 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg">Cancel</button>
                <button onClick={saveGatewayEdit} className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700">Save</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageTransition>
  );
}
