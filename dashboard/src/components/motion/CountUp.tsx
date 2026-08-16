/**
 * @file CountUp.tsx
 * @description Animated number counter that springs from 0 to the target value.
 * Used in dashboard stat cards to give a dynamic feel when numbers load.
 * Supports prefixes, suffixes, and decimal precision.
 *
 * @param value - Target number to animate towards
 * @param duration - Animation duration in seconds (default: 1.2)
 * @param className - CSS classes for the text element
 * @param suffix - Text appended after the number (e.g., '%', ' km')
 * @param prefix - Text prepended before the number (e.g., 'R')
 * @param decimals - Number of decimal places to display
 */
import { useEffect, useState, useRef } from 'react';
import { motion, useSpring, useTransform } from 'framer-motion';

interface CountUpProps {
  value: number;
  duration?: number;
  className?: string;
  suffix?: string;
  prefix?: string;
  decimals?: number;
}

export default function CountUp({
  value,
  duration = 1.2,
  className = '',
  suffix = '',
  prefix = '',
  decimals = 0,
}: CountUpProps) {
  const springValue = useSpring(0, { duration: duration * 1000, bounce: 0 });
  const displayValue = useTransform(springValue, (v) =>
    `${prefix}${v.toFixed(decimals)}${suffix}`
  );
  const ref = useRef<HTMLSpanElement>(null);
  const [hasAnimated, setHasAnimated] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated) {
          springValue.set(value);
          setHasAnimated(true);
        }
      },
      { threshold: 0.3 }
    );

    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [value, hasAnimated, springValue]);

  return <motion.span ref={ref} className={className}>{displayValue}</motion.span>;
}
