/**
 * @file motion/index.ts
 * @description Barrel export for all Framer Motion animation primitives.
 * Import from `@/components/motion` to access page transitions, animated
 * cards, progress bars, count-up numbers, stagger lists, and skeleton loaders.
 */
export { default as PageTransition } from './PageTransition';
export { default as StaggerList, staggerItem } from './StaggerList';
export { default as AnimatedCard } from './AnimatedCard';
export { default as AnimatedProgressBar } from './AnimatedProgressBar';
export { default as CountUp } from './CountUp';
export { default as SkeletonLoader, CardSkeleton, TableRowSkeleton } from './SkeletonLoader';
