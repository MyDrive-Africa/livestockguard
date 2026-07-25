import { motion } from 'framer-motion';
import { PageTransition } from '@/components/motion';

const demoGeofences = [
  { id: '1', name: 'Main Paddock', type: 'inclusion', active: true, animals: 12, area: '45 ha' },
  { id: '2', name: 'Water Source Zone', type: 'inclusion', active: true, animals: 3, area: '2 ha' },
  { id: '3', name: 'Road Boundary', type: 'exclusion', active: true, animals: 0, area: '8 ha' },
  { id: '4', name: 'Winter Grazing', type: 'inclusion', active: false, animals: 0, area: '30 ha' },
  { id: '5', name: 'Neighbors Property', type: 'exclusion', active: true, animals: 0, area: '120 ha' },
];

const cardVariants = {
  hidden: { opacity: 0, y: 16, scale: 0.98 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { delay: i * 0.08, duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] },
  }),
};

export default function GeofencesPage() {
  return (
    <PageTransition className="p-6 bg-gray-50 dark:bg-gray-900 min-h-full theme-transition">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Geofences</h1>
        <button className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors">
          + Create Geofence
        </button>
      </div>

      <div className="grid gap-4">
        {demoGeofences.map((fence, i) => (
          <motion.div
            key={fence.id}
            custom={i}
            variants={cardVariants}
            initial="hidden"
            animate="show"
            whileHover={{ scale: 1.01, boxShadow: '0 8px 25px rgba(0,0,0,0.08)' }}
            className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 flex items-center justify-between transition-colors theme-transition"
          >
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                fence.type === 'inclusion' ? 'bg-green-100 dark:bg-green-900/30' : 'bg-red-100 dark:bg-red-900/30'
              }`}>
                <span className="text-lg">{fence.type === 'inclusion' ? '🟢' : '🔴'}</span>
              </div>
              <div>
                <h3 className="font-medium text-gray-900 dark:text-white">{fence.name}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {fence.type} &middot; {fence.area} &middot; {fence.animals} animals inside
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 text-xs rounded-full font-medium ${
                fence.active
                  ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
              }`}>
                {fence.active ? 'Active' : 'Inactive'}
              </span>
              <button className="text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300">
                <span>...</span>
              </button>
            </div>
          </motion.div>
        ))}
      </div>
    </PageTransition>
  );
}
