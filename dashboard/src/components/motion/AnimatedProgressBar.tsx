/**
 * @file AnimatedProgressBar.tsx
 * @description Horizontal progress bar with animated fill using Framer Motion.
 * Animates from 0% to the target percentage on mount with a spring easing.
 *
 * @param percentage - Fill percentage (0–100)
 * @param color - Tailwind background colour class for the fill (e.g., 'bg-green-500')
 * @param delay - Animation start delay in seconds
 */
import { motion } from 'framer-motion';

interface AnimatedProgressBarProps {
  percentage: number;
  color: string;
  delay?: number;
}

export default function AnimatedProgressBar({ percentage, color, delay = 0 }: AnimatedProgressBarProps) {
  return (
    <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
      <motion.div
        className={`h-full rounded-full ${color}`}
        initial={{ width: 0 }}
        animate={{ width: `${percentage}%` }}
        transition={{ duration: 0.8, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      />
    </div>
  );
}
