/**
 * @file AlertsPage.tsx
 * @description Alert management dashboard showing geofence breaches, theft detections,
 * low battery warnings, and device offline notifications. Alerts are colour-coded
 * by severity (critical → info) and update in real-time via WebSocket.
 *
 * Features:
 * - Severity-grouped alert list with time-based filtering
 * - Real-time new alert notifications (pushed via WebSocket)
 * - Acknowledge/dismiss individual alerts
 * - Filter by alert type, severity, and date range
 * - Links to MapPage for breach location context
 *
 * @see useRealtimeStore — Pushes new alerts to the page in real-time
 * @see useAuthStore — Scopes alerts to the current farm
 */
import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useRealtimeStore } from '@/stores/realtimeStore';
import { useAuthStore } from '@/stores/authStore';
import { apiClient } from '@/api/client';
import { PageTransition } from '@/components/motion';
import type { Alert } from '@/types';

const severityStyles: Record<string, string> = {
  critical: 'border-l-red-600 bg-red-50 dark:bg-red-900/20',
  high: 'border-l-orange-500 bg-orange-50 dark:bg-orange-900/20',
  medium: 'border-l-yellow-500 bg-yellow-50 dark:bg-yellow-900/20',
  low: 'border-l-blue-400 bg-blue-50 dark:bg-blue-900/20',
  info: 'border-l-gray-400 bg-gray-50 dark:bg-gray-800',
};

const severityBadge: Record<string, string> = {
  critical: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  high: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
  low: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  info: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
};

const alertTypeLabels: Record<string, string> = {
  geofence_breach: 'Geofence Breach',
  theft_detected: 'Theft Detected',
  low_battery: 'Low Battery',
  device_offline: 'Device Offline',
  unusual_activity: 'Unusual Activity',
  no_movement: 'No Movement',
  temperature_alert: 'Temperature Alert',
};

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const currentFarm = useAuthStore((state) => state.currentFarm);
  const realtimeAlerts = useRealtimeStore((state) => state.alerts);

  // Fetch alerts from API
  const fetchAlerts = useCallback(async () => {
    try {
      setError(null);
      const params: Record<string, string> = {};
      if (currentFarm) params.farm_id = currentFarm;
      if (filterSeverity !== 'all') params.severity = filterSeverity;
      if (filterStatus !== 'all') params.status = filterStatus;

      const resp = await apiClient.get('/api/alerts', { params });
      setAlerts(resp.data);
    } catch (err: any) {
      setError('Failed to load alerts');
      console.error('Alerts fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [currentFarm, filterSeverity, filterStatus]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  // Merge real-time alerts into the list (new alerts come via WebSocket)
  useEffect(() => {
    if (realtimeAlerts.length === 0) return;
    setAlerts((prev) => {
      const existingIds = new Set(prev.map((a) => a.id));
      const newAlerts = realtimeAlerts.filter((a) => !existingIds.has(a.id));
      if (newAlerts.length === 0) return prev;
      return [...newAlerts, ...prev];
    });
  }, [realtimeAlerts]);

  // Acknowledge alert
  async function handleAcknowledge(alertId: string) {
    setActionLoading(alertId);
    try {
      await apiClient.put(`/api/alerts/${alertId}/acknowledge`);
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId ? { ...a, status: 'acknowledged' } : a
        )
      );
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    } finally {
      setActionLoading(null);
    }
  }

  // Resolve alert
  async function handleResolve(alertId: string) {
    setActionLoading(alertId);
    try {
      await apiClient.put(`/api/alerts/${alertId}/resolve`);
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId ? { ...a, status: 'resolved' } : a
        )
      );
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    } finally {
      setActionLoading(null);
    }
  }

  const activeCount = alerts.filter((a) => a.status === 'active').length;
  const criticalCount = alerts.filter((a) => a.severity === 'critical' && a.status === 'active').length;

  return (
    <PageTransition className="p-6 h-full overflow-y-auto bg-gray-50 dark:bg-gray-900 theme-transition">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Alerts</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {activeCount} active{criticalCount > 0 && ` (${criticalCount} critical)`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
          </select>
          <button
            onClick={fetchAlerts}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full"></div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4">
          <p className="text-red-700 dark:text-red-400">{error}</p>
          <button onClick={fetchAlerts} className="text-sm text-red-600 dark:text-red-400 underline mt-1">
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && alerts.length === 0 && (
        <div className="text-center py-12">
          <div className="text-4xl mb-3">🔔</div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white">No alerts</h3>
          <p className="text-gray-500 dark:text-gray-400 mt-1">All systems are operating normally.</p>
        </div>
      )}

      {/* Alerts list */}
      {!loading && alerts.length > 0 && (
        <div className="space-y-3">
          {alerts.map((alert, i) => (
            <motion.div
              key={alert.id}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05, duration: 0.3 }}
              className={`border-l-4 rounded-lg p-4 transition-all ${severityStyles[alert.severity] || severityStyles.info}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span
                      className={`px-2 py-0.5 text-xs font-medium rounded-full ${severityBadge[alert.severity] || severityBadge.info}`}
                    >
                      {alert.severity}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">
                      {alertTypeLabels[alert.alert_type] || alert.alert_type}
                    </span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {timeAgo(alert.created_at)}
                    </span>
                  </div>
                  <p className="font-medium text-gray-900 dark:text-white truncate">{alert.message || 'Alert triggered'}</p>
                  {alert.animal_name && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Animal: {alert.animal_name}</p>
                  )}
                </div>

                <div className="flex items-center gap-2 ml-4 shrink-0">
                  {alert.status === 'active' && (
                    <>
                      <button
                        onClick={() => handleAcknowledge(alert.id)}
                        disabled={actionLoading === alert.id}
                        className="px-3 py-1.5 text-sm bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 disabled:opacity-50"
                      >
                        {actionLoading === alert.id ? '...' : 'Acknowledge'}
                      </button>
                      <button
                        onClick={() => handleResolve(alert.id)}
                        disabled={actionLoading === alert.id}
                        className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                      >
                        Resolve
                      </button>
                    </>
                  )}
                  {alert.status === 'acknowledged' && (
                    <button
                      onClick={() => handleResolve(alert.id)}
                      disabled={actionLoading === alert.id}
                      className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                    >
                      Resolve
                    </button>
                  )}
                  <span
                    className={`px-2 py-0.5 text-xs rounded-full ${
                      alert.status === 'active'
                        ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                        : alert.status === 'acknowledged'
                          ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
                          : 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                    }`}
                  >
                    {alert.status}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </PageTransition>
  );
}
