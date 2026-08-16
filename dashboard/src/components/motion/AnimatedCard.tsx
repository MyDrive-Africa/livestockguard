/**
 * @file AnimatedCard.tsx
 * @description Reusable card wrapper with entrance animation (fade + slide up)
 * and hover lift effect. Used across dashboard pages for stat cards, device
 * cards, and summary panels.
 *
 * @param children - Card content
 * @param className - Additional CSS classes (typically includes bg, padding, border-radius)
 * @param delay - Animation delay in seconds for staggered card appearances
 */
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

interface AnimatedCardProps {
  children: ReactNode;
  className?: string;
  delay?: number;
}

export default function AnimatedCard({ children, className = '', delay = 0 }: AnimatedCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={{ y: -2, boxShadow: '0 8px 25px rgba(0,0,0,0.1)' }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
