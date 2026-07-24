const demoGeofences = [
  { id: '1', name: 'Main Paddock', type: 'inclusion', active: true, animals: 12, area: '45 ha' },
  { id: '2', name: 'Water Source Zone', type: 'inclusion', active: true, animals: 3, area: '2 ha' },
  { id: '3', name: 'Road Boundary', type: 'exclusion', active: true, animals: 0, area: '8 ha' },
  { id: '4', name: 'Winter Grazing', type: 'inclusion', active: false, animals: 0, area: '30 ha' },
  { id: '5', name: 'Neighbors Property', type: 'exclusion', active: true, animals: 0, area: '120 ha' },
];

export default function GeofencesPage() {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Geofences</h1>
        <button className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors">
          + Create Geofence
        </button>
      </div>

      <div className="grid gap-4">
        {demoGeofences.map((fence) => (
          <div
            key={fence.id}
            className="bg-white rounded-xl shadow-sm border p-4 flex items-center justify-between hover:shadow-md transition-shadow"
          >
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                fence.type === 'inclusion' ? 'bg-green-100' : 'bg-red-100'
              }`}>
                <span className="text-lg">{fence.type === 'inclusion' ? '🟢' : '🔴'}</span>
              </div>
              <div>
                <h3 className="font-medium text-gray-900">{fence.name}</h3>
                <p className="text-sm text-gray-500">
                  {fence.type} &middot; {fence.area} &middot; {fence.animals} animals inside
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 text-xs rounded-full font-medium ${
                fence.active
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {fence.active ? 'Active' : 'Inactive'}
              </span>
              <button className="text-gray-400 hover:text-gray-600">
                <span>...</span>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
