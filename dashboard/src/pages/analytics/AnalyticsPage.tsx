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

export default function AnalyticsPage() {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryCards.map((card) => (
          <div key={card.label} className="bg-white rounded-xl shadow-sm border p-4">
            <p className="text-sm text-gray-600">{card.label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{card.value}</p>
            {card.change && (
              <p className={`text-sm mt-1 ${card.change.startsWith('+') ? 'text-green-600' : 'text-red-600'}`}>
                {card.change} vs yesterday
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Activity Breakdown */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Activity Breakdown (Today)</h2>
        <div className="space-y-3">
          {activityBreakdown.map((activity) => (
            <div key={activity.label} className="flex items-center gap-3">
              <span className="w-20 text-sm text-gray-600">{activity.label}</span>
              <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                <div
                  className={`h-full rounded-full ${activity.color}`}
                  style={{ width: `${activity.percentage}%` }}
                ></div>
              </div>
              <span className="w-12 text-sm text-right text-gray-700 font-medium">
                {activity.percentage}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Geofence Compliance */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">Geofence Compliance (Last 7 Days)</h2>
        </div>
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Geofence</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Compliance</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Breaches</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Avg. Return Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {complianceRows.map((row) => (
              <tr key={row.fence} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{row.fence}</td>
                <td className="px-4 py-3">
                  <span className={`font-medium ${row.compliance >= 98 ? 'text-green-600' : row.compliance >= 95 ? 'text-yellow-600' : 'text-red-600'}`}>
                    {row.compliance}%
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-600">{row.breaches}</td>
                <td className="px-4 py-3 text-gray-600">{row.avgReturn}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
