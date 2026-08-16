/**
 * @file StaggerList.tsx
 * @description Container component that staggers the entrance animation of its
 * children. Each child fades and slides in sequentially with a configurable delay.
 * Pair with the exported `staggerItem` variants on child elements.
 *
 * @param children - List items to stagger
 * @param className - CSS classes for the container
 * @param staggerDelay - Delay between each child animation (seconds)
 *
 * @example
 * ```tsx
 * <StaggerList>
 *   {items.map(item => (
 *     <motion.div key={item.id} variants={staggerItem}>{item.name}</motion.div>
 *   ))}
 * </StaggerList>
 * ```
 */
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

interface StaggerListProps {
  children: ReactNode;
  className?: string;
  staggerDelay?: number;
}

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.06,
    },
  },
};

export const staggerItem = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
};

export default function StaggerList({ children, className = '', staggerDelay = 0.06 }: StaggerListProps) {
  return (
    <motion.div
      variants={{
        ...container,
        show: { ...container.show, transition: { staggerChildren: staggerDelay } },
      }}
      initial="hidden"
      animate="show"
      className={className}
    >
      {children}
    </motion.div>
  );
}
