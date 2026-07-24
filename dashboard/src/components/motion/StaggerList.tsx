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
