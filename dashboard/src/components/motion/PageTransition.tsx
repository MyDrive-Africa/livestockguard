/**
 * @file PageTransition.tsx
 * @description Framer Motion wrapper that applies a fade-and-slide entrance
 * animation to page-level content. Used by all page components to provide
 * consistent route transition effects.
 *
 * @param children - Page content to animate
 * @param className - Additional CSS classes for the wrapper div
 */
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

interface PageTransitionProps {
  children: ReactNode;
  className?: string;
}

export default function PageTransition({ children, className = '' }: PageTransitionProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
