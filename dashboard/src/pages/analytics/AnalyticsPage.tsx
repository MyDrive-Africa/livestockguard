import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { PageTransition, AnimatedCard } from '@/components/motion';
import { useThemeStore } from '@/stores/themeStore';
import { downloadCSV, printReport } from '@/utils/export';
import {
  useDistance,
  useActivity,
  useCompliance,
  useInsightsDashboard,
  type DateRange,
  type DistanceBucket,
} from '@/hooks/useAnalytics';

// ─── Helpers ─────────────────────────────────────────

function formatBucketLabel(isoStr: string, interval: string): string {
  const d = new Date(isoStr);
  if (interval === '1d') {
    return d.toLocaleDateString('en-ZA', { weekday: 'short' });
  }
  return d.toLocaleTimeString('en-ZA', { hour: '2-digit', minute: '2-digit' });
}

const ACTIVITY_COLORS = {
  grazing: '#22c55e',
  resting: '#3b82f6',
  walking: '#eab308',
  running: '#ef4444',
};

// ─── Component ───────────────────────────────────────

export default function AnalyticsPage() {
  const [dateRange, setDateRange] = useState<DateRange>('7d');
  const resolved = useThemeStore((state) => state.resolved);
  const isDark = resolved === 'dark';

  // Determine interval based on date range
  const distanceInterval = dateRange === '24h' ? '1h' : '1d';
  const activityInterval = dateRange === '24h' ? '1h' : dateRange === '7d' ? '6h' : '1d';

  // Fetch real data from API
  const { data: distanceData, isLoading: distanceLoading } = useDistance(dateRange, distanceInterval);
  const { data: activityData, isLoading: activityLoading } = useActivity(dateRange, activityInterval);
  const { data: complianceData, isLoading: complianceLoading } = useCompliance(dateRange);
  const { data: insightsData } = useInsightsDashboard();

  const isLoading = distanceLoading || activityLoading || complianceLoading;

  // Derived chart data
  const movementChartData = distanceData?.data.map((b: DistanceBucket) => ({
    label: formatBucketLabel(b.time_bucket, distanceInterval),
    distance: b.distance_km,
    animals: b.animals_active,
  })) ?? [];

  const activityPieData = activityData?.summary
    ? [
        { name: 'Grazing', value: activityData.summary.grazing_pct, color: ACTIVITY_COLORS.grazing },
        { name: 'Resting', value: activityData.summary.resting_pct, color: ACTIVITY_COLORS.resting },
        { name: 'Walking', value: activityData.summary.walking_pct, color: ACTIVITY_COLORS.walking },
        { name: 'Running', value: activityData.summary.running_pct, color: ACTIVITY_COLORS.running },
      ]
    : [];

  const complianceDetails = complianceData?.details ?? [];

  // Summary cards from real data
  const totalDistanceKm = distanceData?.total_distance_km ?? 0;
  const latestAnimals = movementChartData.length > 0
    ? movementChartData[movementChartData.length - 1].animals
    : 0;
  const totalAnimals = distanceData?.top_animals?.length ?? 0;
  const overallCompliance = complianceData?.overall_compliance ?? 0;

  const summaryCards = [
    {
      label: `Total Distance (${dateRange})`,
      value: totalDistanceKm.toFixed(1),
      suffix: ' km',
      sparkline: movementChartData.map((d: { distance: number }) => d.distance),
      positive: true,
    },
    {
      label: 'Active Animals',
      value: latestAnimals,
      suffix: totalAnimals > 0 ? ` / ${totalAnimals}` : '',
      sparkline: movementChartData.map((d: { animals: number }) => d.animals),
      positive: true,
    },
    {
      label: 'Grazing %',
      value: activityData?.summary?.grazing_pct?.toFixed(1) ?? '0',
      suffix: '%',
      sparkline: activityData?.data?.map((b) => b.grazing) ?? [],
      positive: true,
    },
    {
      label: 'Geofence Compliance',
      value: overallCompliance.toFixed(1),
      suffix: '%',
      sparkline: complianceDetails.map((d) => d.compliance_rate),
      positive: overallCompliance >= 95,
    },
  ];

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
        <div className="flex items-center gap-3">
          {/* Export buttons */}
          <div className="flex items-center gap-1 no-print">
            <button
              onClick={() => downloadCSV(
                movementChartData,
                [{ key: 'label', label: 'Period' }, { key: 'distance', label: 'Distance (km)' }, { key: 'animals', label: 'Active Animals' }],
                'livestockguard_movement'
              )}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 transition-colors"
            >
              CSV
            </button>
            <button
              onClick={printReport}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 transition-colors"
            >
              PDF
            </button>
          </div>

          {/* Date range picker */}
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
      </div>

      {/* Loading indicator */}
      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <div className="w-4 h-4 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
          Loading analytics data...
        </div>
      )}

      {/* Intelligence Panel — Anomalies & Suggestions */}
      {insightsData && (insightsData.anomalies_active > 0 || insightsData.suggestions_pending > 0 || insightsData.latest_report_summary) && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-5 theme-transition"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Farm Intelligence</h2>
            <div className="flex items-center gap-3">
              {insightsData.anomalies_high > 0 && (
                <span className="px-2 py-1 text-xs font-bold text-red-400 bg-red-900/30 rounded-full">
                  {insightsData.anomalies_high} high severity
                </span>
              )}
              {insightsData.latest_report_date && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  Report: {new Date(insightsData.latest_report_date).toLocaleDateString('en-ZA', { day: 'numeric', month: 'short' })}
                </span>
              )}
            </div>
          </div>

          {/* Report Summary */}
          {insightsData.latest_report_summary && (
            <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
              <p className="text-sm text-blue-800 dark:text-blue-200">{insightsData.latest_report_summary}</p>
            </div>
          )}

          {/* Anomalies + Suggestions Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Anomalies */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Active Anomalies ({insightsData.anomalies_active})
              </h3>
              {insightsData.anomalies.length === 0 ? (
                <p className="text-sm text-green-600 dark:text-green-400">No active anomalies</p>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {insightsData.anomalies.slice(0, 5).map((a) => (
                    <div key={a.id} className="flex items-start gap-2 p-2 rounded-lg bg-gray-50 dark:bg-gray-700/50">
                      <span className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${a.severity === 'high' ? 'bg-red-500' : a.severity === 'medium' ? 'bg-yellow-500' : 'bg-gray-400'}`} />
                      <div className="min-w-0">
                        <p className="text-sm text-gray-900 dark:text-white truncate">
                          {a.animal_name && <span className="font-medium">{a.animal_name} — </span>}
                          {a.anomaly_type.replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{a.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Suggestions */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Pending Suggestions ({insightsData.suggestions_pending})
              </h3>
              {insightsData.suggestions.length === 0 ? (
                <p className="text-sm text-green-600 dark:text-green-400">No pending suggestions</p>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {insightsData.suggestions.slice(0, 5).map((s) => (
                    <div key={s.id} className="flex items-start gap-2 p-2 rounded-lg bg-gray-50 dark:bg-gray-700/50">
                      <span className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${s.priority === 'high' ? 'bg-red-500' : s.priority === 'medium' ? 'bg-yellow-500' : 'bg-gray-400'}`} />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{s.title}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{s.recommended_action}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}

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
              {card.sparkline.length > 1 && (
                <div className="w-16 h-8">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={card.sparkline.map((v: number, idx: number) => ({ v, idx }))}>
                      <Area
                        type="monotone"
                        dataKey="v"
                        stroke={card.positive ? '#22c55e' : '#ef4444'}
                        fill={card.positive ? '#dcfce7' : '#fecaca'}
                        fillOpacity={isDark ? 0.2 : 0.4}
                        strokeWidth={1.5}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </AnimatedCard>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Movement Distance Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 theme-transition"
        >
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Movement Distance</h2>
          {movementChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={movementChartData}>
                <defs>
                  <linearGradient id="distanceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                <XAxis dataKey="label" tick={{ fill: chartColors.text, fontSize: 12 }} />
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
          ) : (
            <div className="h-60 flex items-center justify-center text-gray-400 dark:text-gray-500">
              {distanceLoading ? 'Loading...' : 'No movement data available'}
            </div>
          )}
        </motion.div>

        {/* Activity Donut Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 theme-transition"
        >
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Activity Breakdown</h2>
          {activityPieData.length > 0 && activityPieData.some((d) => d.value > 0) ? (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width="55%" height={200}>
                <PieChart>
                  <Pie
                    data={activityPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                    animationDuration={1000}
                    animationBegin={400}
                  >
                    {activityPieData.map((entry) => (
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
                {activityPieData.map((item) => (
                  <div key={item.name} className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                    <span className="text-sm text-gray-600 dark:text-gray-400 flex-1">{item.name}</span>
                    <span className="text-sm font-medium text-gray-900 dark:text-white">{item.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-52 flex items-center justify-center text-gray-400 dark:text-gray-500">
              {activityLoading ? 'Loading...' : 'No activity data available'}
            </div>
          )}
        </motion.div>
      </div>

      {/* Second Row of Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Geofence Compliance Bar Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.5 }}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 theme-transition"
        >
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Geofence Compliance</h2>
          {complianceDetails.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={complianceDetails.map((d) => ({
                fence: d.geofence_name.length > 15 ? d.geofence_name.slice(0, 15) + '...' : d.geofence_name,
                compliance: d.compliance_rate,
                outside: Math.round((100 - d.compliance_rate) * 10) / 10,
              }))}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                <XAxis dataKey="fence" tick={{ fill: chartColors.text, fontSize: 11 }} />
                <YAxis tick={{ fill: chartColors.text, fontSize: 12 }} domain={[0, 100]} unit="%" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: chartColors.tooltip,
                    border: `1px solid ${chartColors.tooltipBorder}`,
                    borderRadius: 8,
                    color: isDark ? '#f3f4f6' : '#111827',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="compliance" name="Inside %" fill="#22c55e" radius={[4, 4, 0, 0]} animationDuration={1000} />
                <Bar dataKey="outside" name="Outside %" fill="#ef4444" radius={[4, 4, 0, 0]} animationDuration={1000} animationBegin={300} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-52 flex items-center justify-center text-gray-400 dark:text-gray-500">
              {complianceLoading ? 'Loading...' : 'No geofence data available'}
            </div>
          )}
        </motion.div>

        {/* Top Animals by Distance */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6 }}
          className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 theme-transition"
        >
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Top Animals by Distance</h2>
          {(distanceData?.top_animals?.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={distanceData!.top_animals.slice(0, 8).map((a) => ({
                  name: a.animal_name || a.animal_id.slice(0, 8),
                  distance: a.distance_km,
                }))}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                <XAxis type="number" tick={{ fill: chartColors.text, fontSize: 12 }} unit=" km" />
                <YAxis type="category" dataKey="name" tick={{ fill: chartColors.text, fontSize: 11 }} width={80} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: chartColors.tooltip,
                    border: `1px solid ${chartColors.tooltipBorder}`,
                    borderRadius: 8,
                    color: isDark ? '#f3f4f6' : '#111827',
                  }}
                />
                <Bar dataKey="distance" fill="#3b82f6" radius={[0, 4, 4, 0]} animationDuration={1200} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-52 flex items-center justify-center text-gray-400 dark:text-gray-500">
              {distanceLoading ? 'Loading...' : 'No distance data available'}
            </div>
          )}
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
          <span className="text-xs text-gray-500 dark:text-gray-400">{dateRange} period</span>
        </div>
        {complianceDetails.length > 0 ? (
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Geofence</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Compliance</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Points Inside</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Total Points</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {complianceDetails.map((row, i) => (
                <motion.tr
                  key={row.geofence_id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.8 + i * 0.08, duration: 0.3 }}
                  className="hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{row.geofence_name}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-gray-100 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
                        <motion.div
                          className={`h-full rounded-full ${row.compliance_rate >= 98 ? 'bg-green-500' : row.compliance_rate >= 95 ? 'bg-yellow-500' : 'bg-red-500'}`}
                          initial={{ width: 0 }}
                          animate={{ width: `${row.compliance_rate}%` }}
                          transition={{ duration: 0.8, delay: 0.9 + i * 0.1 }}
                        />
                      </div>
                      <span className={`text-sm font-medium ${row.compliance_rate >= 98 ? 'text-green-600 dark:text-green-400' : row.compliance_rate >= 95 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}`}>
                        {row.compliance_rate}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{row.inside_points.toLocaleString()}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{row.total_points.toLocaleString()}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-8 text-center text-gray-400 dark:text-gray-500">
            {complianceLoading ? 'Loading compliance data...' : 'No geofence compliance data available'}
          </div>
        )}
      </motion.div>
    </PageTransition>
  );
}
