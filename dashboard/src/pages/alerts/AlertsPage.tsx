import { useRealtimeStore } from '@/stores/realtimeStore';

const demoAlerts = [
  { id: '1', type: 'geofence_breach', severity: 'high' as const, message: 'Bella has left Main Paddock', animal: 'Bella', time: '2 min ago', status: 'active' as const },
  { id: '2', type: 'low_battery', severity: 'medium' as const, message: 'Max battery below 20%', animal: 'Max', time: '15 min ago', status: 'active' as const },
  { id: '3', type: 'theft_detected', severity: 'critical' as const, message: 'Unusual movement pattern for Duke at night', animal: 'Duke', time: '1 hr ago', status: 'acknowledged' as const },
  { id: '4', type: 'device_offline', severity: 'low' as const, message: 'Device LG-007 has not reported in 6 hours', animal: 'N/A', time: '3 hrs ago', status: 'resolved' as const },
];

const severityStyles = {
  critical: 'border-l-red-600 bg-red-50',
  high: 'border-l-orange-500 bg-orange-50',
  medium: 'border-l-yellow-500 bg-yellow-50',
  low: 'border-l-blue-400 bg-blue-50',
  info: 'border-l-gray-400 bg-gray-50',
};

const severityBadge = {
  critical: 'bg-red-100 text-red-800',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-blue-100 text-blue-800',
  info: 'bg-gray-100 text-gray-800',
};

export default function AlertsPage() {
  const acknowledgeAlert = useRealtimeStore((state) => state.acknowledgeAlert);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
        <div className="flex items-center gap-2">
          <select className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>
      </div>

      <div className="space-y-3">
        {demoAlerts.map((alert) => (
          <div
            key={alert.id}
            className={`border-l-4 rounded-lg p-4 ${severityStyles[alert.severity]}`}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${severityBadge[alert.severity]}`}>
                    {alert.severity}
                  </span>
                  <span className="text-xs text-gray-500">{alert.time}</span>
                </div>
                <p className="font-medium text-gray-900">{alert.message}</p>
                <p className="text-sm text-gray-600 mt-1">Animal: {alert.animal}</p>
              </div>

              <div className="flex items-center gap-2">
                {alert.status === 'active' && (
                  <button
                    onClick={() => acknowledgeAlert(alert.id)}
                    className="px-3 py-1 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                  >
                    Acknowledge
                  </button>
                )}
                <span className={`px-2 py-0.5 text-xs rounded-full ${
                  alert.status === 'active' ? 'bg-red-100 text-red-700' :
                  alert.status === 'acknowledged' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-green-100 text-green-700'
                }`}>
                  {alert.status}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
