import { motion } from 'framer-motion';
import { PageTransition, AnimatedCard, AnimatedProgressBar } from '@/components/motion';

const summaryCards = [
  { label: 'Total Distance Today', value: '47.2 km', change: '+12%' },
  { label: 'Active Animals', value: '24 / 28', change: '' },
  { label: 'Avg. Battery Level', value: '76%', change: '-3%' },
  { label: 'Geofence Compliance', value: '96.4%', change: '+1.2%' },
];

const activityBreakdown = [
  { label: 'Grazing', percentage: 45, color: 'bg-green-500' },
  { label: 'Resting', percentage: 30, color: 'bg-blue-500' },
  { label: 'Walking', percentage: 20, color: 'bg-yellow-500' },
  { label: 'Running', percentage: 5, color: 'bg-red-500' },
];

const complianceRows = [
  { fence: 'Main Paddock', compliance: 98.2, breaches: 3, avgReturn: '4 min' },
  { fence: 'Water Source Zone', compliance: 100, breaches: 0, avgReturn: 'N/A' },
  { fence: 'Road Boundary', compliance: 94.5, breaches: 8, avgReturn: '12 min' },
  { fence: 'Neighbors Property', compliance: 99.1, breaches: 1, avgReturn: '2 min' },
];

const tableRowVariants = {
  hidden: { opacity: 0, x: -10 },
  show: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: 0.4 + i * 0.08, duration: 0.3 },
  }),
};

export default function AnalyticsPage() {
  return (
    <PageTransition className="p-6 space-y-6 bg-gray-50 dark:bg-gray-900 min-h-full theme-transition">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Analytics</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryCards.map((card, i) => (
          <AnimatedCard
            key={card.label}
            delay={i * 0.1}
            className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 theme-transition"
          >
            <p className="text-sm text-gray-600 dark:text-gray-400">{card.label}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{card.value}</p>
            {card.change && (
              <p className={`text-sm mt-1 ${card.change.startsWith('+') ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {card.change} vs yesterday
              </p>
            )}
          </AnimatedCard>
        ))}
      </div>

      {/* Activity Breakdown */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3 }}
        className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 theme-transition"
      >
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Activity Breakdown (Today)</h2>
        <div className="space-y-3">
          {activityBreakdown.map((activity, i) => (
            <div key={activity.label} className="flex items-center gap-3">
              <span className="w-20 text-sm text-gray-600 dark:text-gray-400">{activity.label}</span>
              <AnimatedProgressBar
                percentage={activity.percentage}
                color={activity.color}
                delay={0.4 + i * 0.15}
              />
              <span className="w-12 text-sm text-right text-gray-700 dark:text-gray-300 font-medium">
                {activity.percentage}%
              </span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Geofence Compliance */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.5 }}
        className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden theme-transition"
      >
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Geofence Compliance (Last 7 Days)</h2>
        </div>
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Geofence</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Compliance</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Breaches</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Avg. Return Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {complianceRows.map((row, i) => (
              <motion.tr
                key={row.fence}
                custom={i}
                variants={tableRowVariants}
                initial="hidden"
                animate="show"
                className="hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
              >
                <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{row.fence}</td>
                <td className="px-4 py-3">
                  <span className={`font-medium ${row.compliance >= 98 ? 'text-green-600 dark:text-green-400' : row.compliance >= 95 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}`}>
                    {row.compliance}%
                  </span>
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
