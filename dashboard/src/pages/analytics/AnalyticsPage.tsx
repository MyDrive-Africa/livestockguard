import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { PageTransition, AnimatedCard } from '@/components/motion';
import { useThemeStore } from '@/stores/themeStore';

// ─── Demo Data ───────────────────────────────────────

const movementData = [
  { day: 'Mon', distance: 38.2, animals: 26 },
  { day: 'Tue', distance: 42.5, animals: 27 },
  { day: 'Wed', distance: 35.8, animals: 24 },
  { day: 'Thu', distance: 51.3, animals: 28 },
  { day: 'Fri', distance: 47.1, animals: 27 },
  { day: 'Sat', distance: 44.6, animals: 25 },
  { day: 'Sun', distance: 47.2, animals: 24 },
];

const activityData = [
  { name: 'Grazing', value: 45, color: '#22c55e' },
  { name: 'Resting', value: 30, color: '#3b82f6' },
  { name: 'Walking', value: 20, color: '#eab308' },
  { name: 'Running', value: 5, color: '#ef4444' },
];

const breachData = [
  { fence: 'Main Paddock', breaches: 3, resolved: 3 },
  { fence: 'Water Source', breaches: 0, resolved: 0 },
  { fence: 'Road Boundary', breaches: 8, resolved: 6 },
  { fence: 'Neighbor', breaches: 1, resolved: 1 },
];

const batteryTrend = [
  { hour: '6am', avg: 82 },
  { hour: '9am', avg: 79 },
  { hour: '12pm', avg: 76 },
  { hour: '3pm', avg: 73 },
  { hour: '6pm', avg: 71 },
  { hour: '9pm', avg: 78 },
];

const summaryCards = [
  { label: 'Total Distance Today', value: 47.2, suffix: ' km', change: '+12%', sparkline: movementData.map(d => d.distance) },
  { label: 'Active Animals', value: 24, suffix: ' / 28', change: '', sparkline: movementData.map(d => d.animals) },
  { label: 'Avg. Battery Level', value: 76, suffix: '%', change: '-3%', sparkline: batteryTrend.map(d => d.avg) },
  { label: 'Geofence Compliance', value: 96.4, suffix: '%', change: '+1.2%', sparkline: [94, 95, 96, 97, 96, 97, 96.4] },
];

type DateRange = '24h' | '7d' | '30d';

// ─── Component ───────────────────────────────────────

export default function AnalyticsPage() {
  const [dateRange, setDateRange] = useState<DateRange>('7d');
  const resolved = useThemeStore((state) => state.resolved);
  const isDark = resolved === 'dark';

  const chartColors = {
    grid: isDark ? '#374151' : '#e5e7eb',
    text: isDark ? '#9ca3af' : '#6b7280',
    tooltip: isDark ? '#1f2937' : '#ffffff',
    tooltipBorder: isDark ? '#374151' : '#e5e7eb',
  };

  return (
    <PageTransition className="p-6 space-y-6 bg-gray-50 dark:bg-gray-900 min-h-full theme-transition overflow-y-auto h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Analytics</h1>
        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
          {(['24h', '7d', '30d'] as DateRange[]).map((range) => (
            <button
              key={range}
              onClick={() => setDateRange(range)}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                dateRange === range
                  ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-white font-medium'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards with Sparklines */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryCards.map((card, i) => (
          <AnimatedCard
            key={card.label}
            delay={i * 0.1}
            className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 theme-transition"
          >
            <p className="text-sm text-gray-600 dark:text-gray-400">{card.label}</p>
            <div className="flex items-end justify-between mt-1">
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {card.value}{card.suffix}
              </p>
              {/* Mini sparkline */}
              <div className="w-16 h-8">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={card.sparkline.map((v, idx) => ({ v, idx }))}>
                    <Area
                      type="monotone"
                      dataKey="v"
                      stroke={card.change.startsWith('-') ? '#ef4444' : '#22c55e'}
                      fill={card.change.startsWith('-') ? '#fecaca' : '#dcfce7'}
                      fillOpacity={isDark ? 0.2 : 0.4}
                      strokeWidth={1.5}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
            {card.change && (
              <p className={`text-sm mt-1 ${card.change.startsWith('+') ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {card.change} vs yesterday
              </p>
            )}
          </AnimatedCard>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Movement Distance Line Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 theme-transition"
        >
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Movement Distance</h2>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={movementData}>
              <defs>
                <linearGradient id="distanceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
              <XAxis dataKey="day" tick={{ fill: chartColors.text, fontSize: 12 }} />
              <YAxis tick={{ fill: chartColors.text, fontSize: 12 }} unit=" km" />
              <Tooltip
                contentStyle={{
                  backgroundColor: chartColors.tooltip,
                  border: `1px solid ${chartColors.tooltipBorder}`,
                  borderRadius: 8,
                  color: isDark ? '#f3f4f6' : '#111827',
                }}
              />
              <Area
                type="monotone"
                dataKey="distance"
                stroke="#22c55e"
                fill="url(#distanceGradient)"
                strokeWidth={2}
                animationDuration={1200}
              />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Activity Donut Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 theme-transition"
        >
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Activity Breakdown</h2>
          <div className="flex items-center gap-6">
            <ResponsiveContainer width="55%" height={200}>
              <PieChart>
                <Pie
                  data={activityData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                  animationDuration={1000}
                  animationBegin={400}
                >
                  {activityData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: chartColors.tooltip,
                    border: `1px solid ${chartColors.tooltipBorder}`,
                    borderRadius: 8,
                    color: isDark ? '#f3f4f6' : '#111827',
                  }}
                  formatter={(value: number) => [`${value}%`, '']}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-2">
              {activityData.map((item) => (
                <div key={item.name} className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-sm text-gray-600 dark:text-gray-400 flex-1">{item.name}</span>
                  <span className="text-sm font-medium text-gray-900 dark:text-white">{item.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>

      {/* Second Row of Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Geofence Breach Bar Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.5 }}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 theme-transition"
        >
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Geofence Breaches (7 Days)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={breachData}>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
              <XAxis dataKey="fence" tick={{ fill: chartColors.text, fontSize: 11 }} />
              <YAxis tick={{ fill: chartColors.text, fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: chartColors.tooltip,
                  border: `1px solid ${chartColors.tooltipBorder}`,
                  borderRadius: 8,
                  color: isDark ? '#f3f4f6' : '#111827',
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="breaches" fill="#ef4444" radius={[4, 4, 0, 0]} animationDuration={1000} />
              <Bar dataKey="resolved" fill="#22c55e" radius={[4, 4, 0, 0]} animationDuration={1000} animationBegin={300} />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Battery Trend Line Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6 }}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 theme-transition"
        >
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Avg. Battery Level (Today)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={batteryTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
              <XAxis dataKey="hour" tick={{ fill: chartColors.text, fontSize: 12 }} />
              <YAxis tick={{ fill: chartColors.text, fontSize: 12 }} domain={[60, 100]} unit="%" />
              <Tooltip
                contentStyle={{
                  backgroundColor: chartColors.tooltip,
                  border: `1px solid ${chartColors.tooltipBorder}`,
                  borderRadius: 8,
                  color: isDark ? '#f3f4f6' : '#111827',
                }}
              />
              <Line
                type="monotone"
                dataKey="avg"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={{ fill: '#f59e0b', r: 4 }}
                activeDot={{ r: 6, fill: '#f59e0b', stroke: isDark ? '#1f2937' : '#fff', strokeWidth: 2 }}
                animationDuration={1500}
              />
            </LineChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      {/* Compliance Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.7 }}
        className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden theme-transition"
      >
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Geofence Compliance Detail</h2>
          <span className="text-xs text-gray-500 dark:text-gray-400">Last 7 days</span>
        </div>
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Geofence</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Compliance</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Trend</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Breaches</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Avg. Return</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {[
              { fence: 'Main Paddock', compliance: 98.2, breaches: 3, avgReturn: '4 min', trend: [96, 97, 98, 97, 98, 99, 98.2] },
              { fence: 'Water Source Zone', compliance: 100, breaches: 0, avgReturn: 'N/A', trend: [100, 100, 100, 100, 100, 100, 100] },
              { fence: 'Road Boundary', compliance: 94.5, breaches: 8, avgReturn: '12 min', trend: [92, 93, 91, 94, 93, 95, 94.5] },
              { fence: 'Neighbors Property', compliance: 99.1, breaches: 1, avgReturn: '2 min', trend: [99, 99, 100, 99, 99, 100, 99.1] },
            ].map((row, i) => (
              <motion.tr
                key={row.fence}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.8 + i * 0.08, duration: 0.3 }}
                className="hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
              >
                <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{row.fence}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-16 bg-gray-100 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
                      <motion.div
                        className={`h-full rounded-full ${row.compliance >= 98 ? 'bg-green-500' : row.compliance >= 95 ? 'bg-yellow-500' : 'bg-red-500'}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${row.compliance}%` }}
                        transition={{ duration: 0.8, delay: 0.9 + i * 0.1 }}
                      />
                    </div>
                    <span className={`text-sm font-medium ${row.compliance >= 98 ? 'text-green-600 dark:text-green-400' : row.compliance >= 95 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}`}>
                      {row.compliance}%
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="w-20 h-6">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={row.trend.map((v, idx) => ({ v, idx }))}>
                        <Line
                          type="monotone"
                          dataKey="v"
                          stroke={row.compliance >= 98 ? '#22c55e' : row.compliance >= 95 ? '#eab308' : '#ef4444'}
                          strokeWidth={1.5}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{row.breaches}</td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{row.avgReturn}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </motion.div>
    </PageTransition>
  );
}
