const fleetSummary = [
  { label: 'Total Devices', value: 28 },
  { label: 'Online', value: 24 },
  { label: 'Offline', value: 3 },
  { label: 'Maintenance', value: 1 },
];

const demoDevices = [
  { id: 'LG-001', animal: 'Bella', type: 'Collar', battery: 87, signal: -72, status: 'active' },
  { id: 'LG-002', animal: 'Duke', type: 'Collar', battery: 92, signal: -65, status: 'active' },
  { id: 'LG-003', animal: 'Rosie', type: 'Eartag', battery: 65, signal: -80, status: 'active' },
  { id: 'LG-004', animal: 'Max', type: 'Collar', battery: 18, signal: -75, status: 'low_battery' },
  { id: 'LG-005', animal: 'Daisy', type: 'Eartag', battery: 78, signal: -68, status: 'active' },
  { id: 'LG-006', animal: 'Thunder', type: 'Collar', battery: 91, signal: -70, status: 'active' },
  { id: 'LG-007', animal: 'Storm', type: 'Eartag', battery: 45, signal: 0, status: 'offline' },
];

export default function DevicesPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Devices</h1>
        <button className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700">
          + Register Device
        </button>
      </div>

      {/* Fleet Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {fleetSummary.map((item) => (
          <div key={item.label} className="bg-white rounded-xl shadow-sm border p-4 text-center">
            <p className="text-2xl font-bold text-gray-900">{item.value}</p>
            <p className="text-sm text-gray-600">{item.label}</p>
          </div>
        ))}
      </div>

      {/* Device Table */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Device ID</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Animal</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Type</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Battery</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Signal</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {demoDevices.map((device) => (
              <tr key={device.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-sm font-medium text-gray-900">
                  {device.id}
                </td>
                <td className="px-4 py-3 text-gray-700">{device.animal}</td>
                <td className="px-4 py-3 text-gray-600">{device.type}</td>
                <td className="px-4 py-3">
                  <BatteryIndicator level={device.battery} />
                </td>
                <td className="px-4 py-3">
                  <SignalIndicator rssi={device.signal} />
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={device.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BatteryIndicator({ level }: { level: number }) {
  const color = level > 70 ? 'text-green-600' : level > 30 ? 'text-yellow-600' : 'text-red-600';
  return <span className={`text-sm font-medium ${color}`}>{level}%</span>;
}

function SignalIndicator({ rssi }: { rssi: number }) {
  if (rssi === 0) return <span className="text-sm text-gray-400">N/A</span>;
  const strength = rssi > -70 ? 'Strong' : rssi > -85 ? 'Good' : 'Weak';
  const color = rssi > -70 ? 'text-green-600' : rssi > -85 ? 'text-yellow-600' : 'text-red-600';
  return <span className={`text-sm ${color}`}>{strength} ({rssi} dBm)</span>;
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: 'bg-green-100 text-green-800',
    low_battery: 'bg-yellow-100 text-yellow-800',
    offline: 'bg-gray-100 text-gray-600',
    maintenance: 'bg-blue-100 text-blue-800',
  };
  return (
    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${styles[status] || styles.active}`}>
      {status}
    </span>
  );
}
