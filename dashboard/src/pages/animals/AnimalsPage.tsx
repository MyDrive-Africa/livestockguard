const demoAnimals = [
  { id: '1', name: 'Bella', tagId: 'LG-001', breed: 'Angus', activity: 'Grazing', battery: 87, status: 'active' },
  { id: '2', name: 'Duke', tagId: 'LG-002', breed: 'Hereford', activity: 'Resting', battery: 92, status: 'active' },
  { id: '3', name: 'Rosie', tagId: 'LG-003', breed: 'Holstein', activity: 'Walking', battery: 65, status: 'active' },
  { id: '4', name: 'Max', tagId: 'LG-004', breed: 'Angus', activity: 'Grazing', battery: 43, status: 'low_battery' },
  { id: '5', name: 'Daisy', tagId: 'LG-005', breed: 'Jersey', activity: 'Resting', battery: 78, status: 'active' },
  { id: '6', name: 'Thunder', tagId: 'LG-006', breed: 'Brahman', activity: 'Walking', battery: 91, status: 'active' },
];

function BatteryBadge({ level }: { level: number }) {
  const color = level > 70 ? 'bg-green-100 text-green-800' : level > 30 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800';
  return <span className={`px-2 py-0.5 text-xs rounded-full ${color}`}>{level}%</span>;
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: 'bg-green-100 text-green-800',
    low_battery: 'bg-yellow-100 text-yellow-800',
    offline: 'bg-gray-100 text-gray-800',
  };
  return <span className={`px-2 py-0.5 text-xs rounded-full ${styles[status] || styles.active}`}>{status}</span>;
}

export default function AnimalsPage() {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Animals</h1>
        <button className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors">
          + Add Animal
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Name</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Tag ID</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Breed</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Activity</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Battery</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {demoAnimals.map((animal) => (
              <tr key={animal.id} className="hover:bg-gray-50 cursor-pointer">
                <td className="px-4 py-3 font-medium text-gray-900">{animal.name}</td>
                <td className="px-4 py-3 text-gray-600 font-mono text-sm">{animal.tagId}</td>
                <td className="px-4 py-3 text-gray-600">{animal.breed}</td>
                <td className="px-4 py-3 text-gray-600">{animal.activity}</td>
                <td className="px-4 py-3"><BatteryBadge level={animal.battery} /></td>
                <td className="px-4 py-3"><StatusBadge status={animal.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
