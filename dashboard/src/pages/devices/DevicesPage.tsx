import { motion } from 'framer-motion';
import { PageTransition, AnimatedCard, CountUp } from '@/components/motion';

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
    <PageTransition className="p-6 space-y-6 bg-gray-50 dark:bg-gray-900 min-h-full theme-transition">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Devices</h1>
        <button className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700">
          + Register Device
        </button>
      </div>

      {/* Fleet Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {fleetSummary.map((item, i) => (
          <AnimatedCard key={item.label} delay={i * 0.1} className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 text-center theme-transition">
            <CountUp value={item.value} className="text-2xl font-bold text-gray-900 dark:text-white" />
            <p className="text-sm text-gray-600 dark:text-gray-400">{item.label}</p>
          </AnimatedCard>
        ))}
      </div>

      {/* Device Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3 }}
        className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden theme-transition"
      >
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Device ID</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Animal</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Type</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Battery</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Signal</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {demoDevices.map((device) => (
              <tr key={device.id} className="hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors">
                <td className="px-4 py-3 font-mono text-sm font-medium text-gray-900 dark:text-white">
                  {device.id}
                </td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{device.animal}</td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{device.type}</td>
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
      </motion.div>
    </PageTransition>
  );
}

function BatteryIndicator({ level }: { level: number }) {
  const color = level > 70 ? 'text-green-600 dark:text-green-400' : level > 30 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400';
  return <span className={`text-sm font-medium ${color}`}>{level}%</span>;
}

function SignalIndicator({ rssi }: { rssi: number }) {
  if (rssi === 0) return <span className="text-sm text-gray-400 dark:text-gray-500">N/A</span>;
  const strength = rssi > -70 ? 'Strong' : rssi > -85 ? 'Good' : 'Weak';
  const color = rssi > -70 ? 'text-green-600 dark:text-green-400' : rssi > -85 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400';
  return <span className={`text-sm ${color}`}>{strength} ({rssi} dBm)</span>;
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
    low_battery: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
    offline: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
    maintenance: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  };
  return (
    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${styles[status] || styles.active}`}>
      {status}
    </span>
  );
}
