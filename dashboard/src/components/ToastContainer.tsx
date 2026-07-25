import { AnimatePresence, motion } from 'framer-motion';
import { useToastStore, type Toast, type ToastSeverity } from '@/stores/toastStore';

const severityConfig: Record<ToastSeverity, { bg: string; icon: string; border: string }> = {
  critical: { bg: 'bg-red-50 dark:bg-red-900/30', icon: '🚨', border: 'border-l-red-600' },
  high: { bg: 'bg-orange-50 dark:bg-orange-900/30', icon: '⚠️', border: 'border-l-orange-500' },
  medium: { bg: 'bg-yellow-50 dark:bg-yellow-900/30', icon: '⚡', border: 'border-l-yellow-500' },
  low: { bg: 'bg-blue-50 dark:bg-blue-900/30', icon: 'ℹ️', border: 'border-l-blue-400' },
  info: { bg: 'bg-gray-50 dark:bg-gray-800', icon: '💬', border: 'border-l-gray-400' },
  success: { bg: 'bg-green-50 dark:bg-green-900/30', icon: '✓', border: 'border-l-green-500' },
};

function ToastItem({ toast }: { toast: Toast }) {
  const removeToast = useToastStore((state) => state.removeToast);
  const config = severityConfig[toast.severity] || severityConfig.info;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 80, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 80, scale: 0.9 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      className={`relative w-80 border-l-4 ${config.border} ${config.bg} rounded-lg shadow-lg dark:shadow-xl dark:shadow-black/20 p-4 pointer-events-auto`}
    >
      <button
        onClick={() => removeToast(toast.id)}
        className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 text-sm"
        aria-label="Dismiss"
      >
        ✕
      </button>
      <div className="flex items-start gap-3">
        <span className="text-lg shrink-0">{config.icon}</span>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-gray-900 dark:text-white text-sm truncate">
            {toast.title}
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5 line-clamp-2">
            {toast.message}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

export default function ToastContainer() {
  const toasts = useToastStore((state) => state.toasts);

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-3 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} />
        ))}
      </AnimatePresence>
    </div>
  );
}
