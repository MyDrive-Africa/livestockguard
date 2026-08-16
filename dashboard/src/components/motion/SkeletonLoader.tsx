/**
 * @file SkeletonLoader.tsx
 * @description Animated placeholder skeletons shown while data is loading.
 * Provides a pulsing opacity animation to indicate content is being fetched.
 * Includes pre-built variants for cards and table rows.
 *
 * Exports:
 * - `SkeletonLoader` — Generic skeleton block (configurable count)
 * - `CardSkeleton` — Pre-styled card placeholder
 * - `TableRowSkeleton` — Pre-styled table row placeholder
 */
import { motion } from 'framer-motion';

interface SkeletonLoaderProps {
  className?: string;
  count?: number;
}

function SkeletonPulse({ className = '' }: { className?: string }) {
  return (
    <motion.div
      className={`bg-gray-200 rounded-lg ${className}`}
      animate={{ opacity: [0.5, 1, 0.5] }}
      transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-4 space-y-3">
      <SkeletonPulse className="h-4 w-24" />
      <SkeletonPulse className="h-8 w-16" />
      <SkeletonPulse className="h-3 w-20" />
    </div>
  );
}

export function TableRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-4 py-3">
      <SkeletonPulse className="h-4 w-20" />
      <SkeletonPulse className="h-4 w-16" />
      <SkeletonPulse className="h-4 w-24" />
      <SkeletonPulse className="h-4 w-12" />
    </div>
  );
}

export default function SkeletonLoader({ className = '', count = 4 }: SkeletonLoaderProps) {
  return (
    <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}
