/**
 * @file AnalyticsPage.tsx
 * @description Farm analytics dashboard with interactive charts for movement distance,
 * activity classification, geofence compliance, and AI-powered insights. Supports
 * multiple date ranges and CSV/print export.
 *
 * Features:
 * - Distance travelled chart (area chart, per-animal breakdown)
 * - Activity classification (grazing/resting/walking/running pie + time-series)
 * - Geofence compliance scores by category
 * - AI-powered insights dashboard (anomalies, suggestions, reports)
 * - Date range selector (24h, 7d, 30d)
 * - CSV export and print-friendly report generation
 *
 * @see useDistance — TanStack Query hook for distance data
 * @see useActivity — TanStack Query hook for activity classification
 * @see useCompliance — TanStack Query hook for compliance scores
 * @see useInsightsDashboard — TanStack Query hook for AI insights
 */
import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { PageTransition, AnimatedCard } from '@/components/motion';
import { useThemeStore } from '@/stores/themeStore';
import { useAuthStore } from '@/stores/authStore';
import { apiClient } from '@/api/client';
import { downloadCSV, printReport } from '@/utils/export';
import {
  useDistance,
  useActivity,
  useCompliance,
  useInsightsDashboard,
  type DateRange,
  type DistanceBucket,
} from '@/hooks/useAnalytics';
import { useEffect } from 'react';

interface Farm {
  id: string;
  name: string;
}

type ViewMode = 'charts' | 'insights';
type ComplianceCategory = 'boundary' | 'exclusion' | 'grazing' | 'infrastructure' | 'all';

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
  const [viewMode, setViewMode] = useState<ViewMode>('charts');
  const [complianceCategory, setComplianceCategory] = useState<ComplianceCategory>('boundary');
  const [farms, setFarms] = useState<Farm[]>([]);
  const currentFarm = useAuthStore((s) => s.currentFarm);
  const switchFarm = useAuthStore((s) => s.switchFarm);
  const resolved = useThemeStore((state) => state.resolved);
  const isDark = resolved === 'dark';

  // Load available farms
  useEffect(() => {
    async function loadFarms() {
      try {
        const resp = await apiClient.get('/api/farms');
        setFarms(resp.data);
      } catch {
        try {
          const resp = await apiClient.get('/api/v1/assignments/me/farms');
          setFarms(resp.data.map((f: any) => ({ id: f.farm_id, name: f.farm_name })));
        } catch {
          // no farms
        }
      }
    }
    loadFarms();
  }, []);

  // Determine interval based on date range
  const distanceInterval = dateRange === '24h' ? '1h' : '1d';
  const activityInterval = dateRange === '24h' ? '1h' : dateRange === '7d' ? '6h' : '1d';

  // Fetch real data from API
  const { data: distanceData, isLoading: distanceLoading } = useDistance(dateRange, distanceInterval);
  const { data: activityData, isLoading: activityLoading } = useActivity(dateRange, activityInterval);
  const { data: complianceData, isLoading: complianceLoading } = useCompliance(dateRange, undefined, complianceCategory);
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
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Analytics</h1>
          {/* Farm Picker */}
          {farms.length > 1 && (
            <select
              value={currentFarm || ''}
              onChange={(e) => switchFarm(e.target.value)}
              className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-green-500"
              aria-label="Select farm"
            >
              {farms.map((farm) => (
                <option key={farm.id} value={farm.id}>{farm.name}</option>
              ))}
            </select>
          )}
          {farms.length === 1 && (
            <span className="text-sm text-gray-500 dark:text-gray-400">{farms[0]?.name}</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            <button
              onClick={() => setViewMode('charts')}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors flex items-center gap-1.5 ${
                viewMode === 'charts'
                  ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-white font-medium'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
              aria-label="Show charts view"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Charts
            </button>
            <button
              onClick={() => setViewMode('insights')}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors flex items-center gap-1.5 ${
                viewMode === 'insights'
                  ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-white font-medium'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
              aria-label="Show insights view"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              Insights
              {insightsData && insightsData.anomalies_active > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs font-bold bg-red-500 text-white rounded-full min-w-[18px] text-center">
                  {insightsData.anomalies_active}
                </span>
              )}
            </button>
          </div>

          {/* Export buttons (charts view only) */}
          {viewMode === 'charts' && (
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
          )}

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

      {/* Summary Cards (always visible) */}
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

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* CHARTS VIEW                                                            */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {viewMode === 'charts' && (
        <>
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
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Geofence Compliance</h2>
                <select
                  value={complianceCategory}
                  onChange={(e) => setComplianceCategory(e.target.value as ComplianceCategory)}
                  className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-green-500"
                  aria-label="Filter geofence category"
                >
                  <option value="boundary">Boundaries</option>
                  <option value="grazing">Grazing Camps</option>
                  <option value="exclusion">Exclusion Zones</option>
                  <option value="infrastructure">Infrastructure</option>
                  <option value="all">All Geofences</option>
                </select>
              </div>
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
              <div className="flex items-center gap-3">
                <select
                  value={complianceCategory}
                  onChange={(e) => setComplianceCategory(e.target.value as ComplianceCategory)}
                  className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-green-500"
                  aria-label="Filter geofence category"
                >
                  <option value="boundary">Boundaries</option>
                  <option value="grazing">Grazing Camps</option>
                  <option value="exclusion">Exclusion Zones</option>
                  <option value="infrastructure">Infrastructure</option>
                  <option value="all">All Geofences</option>
                </select>
                <span className="text-xs text-gray-500 dark:text-gray-400">{dateRange} period</span>
              </div>
            </div>
            {complianceDetails.length > 0 ? (
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                  <tr>
                    <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Geofence</th>
                    <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Type</th>
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
                    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                      row.fence_type === 'exclusion'
                        ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                        : 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
                    }`}>
                      {row.fence_type === 'exclusion' ? 'Exclusion' : 'Inclusion'}
                    </span>
                  </td>
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
        </>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* INSIGHTS VIEW                                                          */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {viewMode === 'insights' && (
        <>
          {/* Intelligence Overview */}
          {insightsData && (
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

              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-red-500">{insightsData.anomalies_active}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Active Anomalies</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-orange-500">{insightsData.anomalies_high}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">High Severity</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-blue-500">{insightsData.suggestions_pending}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Suggestions</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-yellow-500">{insightsData.suggestions_high}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">High Priority</p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Anomalies & Suggestions split */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Anomalies List */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.2 }}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-5 theme-transition"
            >
              <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                Active Anomalies
                {insightsData && insightsData.anomalies.length > 0 && (
                  <span className="text-xs text-gray-400 font-normal">({insightsData.anomalies.length})</span>
                )}
              </h3>
              {(!insightsData || insightsData.anomalies.length === 0) ? (
                <div className="p-6 text-center">
                  <p className="text-sm text-green-600 dark:text-green-400">No active anomalies detected</p>
                  <p className="text-xs text-gray-400 mt-1">All systems operating normally</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[500px] overflow-y-auto">
                  {insightsData.anomalies.map((a) => (
                    <div key={a.id} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 border-l-3 border-l-4" style={{ borderLeftColor: a.severity === 'high' ? '#ef4444' : a.severity === 'medium' ? '#f59e0b' : '#6b7280' }}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          {a.anomaly_type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                        </span>
                        <span className={`px-2 py-0.5 text-xs font-bold rounded-full uppercase ${
                          a.severity === 'high' ? 'bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400' :
                          a.severity === 'medium' ? 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-600 dark:text-yellow-400' :
                          'bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
                        }`}>
                          {a.severity}
                        </span>
                      </div>
                      {a.animal_name && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Animal: {a.animal_name}</p>
                      )}
                      <p className="text-sm text-gray-600 dark:text-gray-300">{a.description}</p>
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                        {new Date(a.detected_at).toLocaleString('en-ZA', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>

            {/* Suggestions List */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.3 }}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-5 theme-transition"
            >
              <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                Suggestions
                {insightsData && insightsData.suggestions.length > 0 && (
                  <span className="text-xs text-gray-400 font-normal">({insightsData.suggestions.length})</span>
                )}
              </h3>
              {(!insightsData || insightsData.suggestions.length === 0) ? (
                <div className="p-6 text-center">
                  <p className="text-sm text-green-600 dark:text-green-400">No pending suggestions</p>
                  <p className="text-xs text-gray-400 mt-1">Farm operations look good</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[500px] overflow-y-auto">
                  {insightsData.suggestions.map((s) => (
                    <div key={s.id} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 border-l-4" style={{ borderLeftColor: s.priority === 'high' ? '#ef4444' : s.priority === 'medium' ? '#f59e0b' : '#6b7280' }}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs px-2 py-0.5 rounded-full bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 capitalize">
                          {s.category}
                        </span>
                        <span className={`px-2 py-0.5 text-xs font-bold rounded-full uppercase ${
                          s.priority === 'high' ? 'bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400' :
                          s.priority === 'medium' ? 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-600 dark:text-yellow-400' :
                          'bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
                        }`}>
                          {s.priority}
                        </span>
                      </div>
                      <p className="text-sm font-medium text-gray-900 dark:text-white mt-2">{s.title}</p>
                      <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">{s.description}</p>
                      <div className="mt-2 p-2 bg-green-50 dark:bg-green-900/20 rounded border border-green-200 dark:border-green-800">
                        <p className="text-xs text-gray-500 dark:text-gray-400 font-medium uppercase mb-0.5">Recommended</p>
                        <p className="text-xs text-green-700 dark:text-green-300">{s.recommended_action}</p>
                      </div>
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                        {new Date(s.created_at).toLocaleString('en-ZA', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          </div>
        </>
      )}
    </PageTransition>
  );
}
