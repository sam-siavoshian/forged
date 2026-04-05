import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import type { RefObject } from 'react';
import { motion, useAnimationControls } from 'framer-motion';
import { v4 as uuidv4 } from 'uuid';

import { cn } from '@/lib/utils';
import { useDimensions } from '@/hooks/use-debounced-dimensions';

interface PixelTrailProps {
  pixelSize: number;
  fadeDuration?: number;
  delay?: number;
  className?: string;
  pixelClassName?: string;
  /**
   * When set, mousemove is listened on this element (bubbling from inputs/buttons)
   * and the trail layer stays pointer-events-none so hovers/clicks reach the UI.
   */
  interactionRootRef?: RefObject<HTMLElement | null>;
  /** No trail under this box — effect only "around" (margins / ring). */
  contentExclusionRef?: RefObject<HTMLElement | null>;
}

const PixelTrail: React.FC<PixelTrailProps> = ({
  pixelSize = 20,
  fadeDuration = 500,
  delay = 0,
  className,
  pixelClassName,
  interactionRootRef,
  contentExclusionRef,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const dimensions = useDimensions(containerRef);
  const trailId = useRef(uuidv4());

  const firePixelAtClient = useCallback(
    (clientX: number, clientY: number) => {
      if (!containerRef.current) return;

      const ex = contentExclusionRef?.current;
      if (ex) {
        const r = ex.getBoundingClientRect();
        const pad = 14;
        if (
          clientX >= r.left - pad &&
          clientX <= r.right + pad &&
          clientY >= r.top - pad &&
          clientY <= r.bottom + pad
        ) {
          return;
        }
      }

      const rect = containerRef.current.getBoundingClientRect();
      const x = Math.floor((clientX - rect.left) / pixelSize);
      const y = Math.floor((clientY - rect.top) / pixelSize);

      const pixelElement = document.getElementById(
        `${trailId.current}-pixel-${x}-${y}`
      );
      if (pixelElement) {
        const animatePixel = (pixelElement as any).__animatePixel;
        if (animatePixel) animatePixel();
      }
    },
    [pixelSize, contentExclusionRef]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      firePixelAtClient(e.clientX, e.clientY);
    },
    [firePixelAtClient]
  );

  useEffect(() => {
    const root = interactionRootRef?.current;
    if (!root) return;

    const handler = (e: MouseEvent) => {
      firePixelAtClient(e.clientX, e.clientY);
    };
    root.addEventListener('mousemove', handler);
    return () => root.removeEventListener('mousemove', handler);
  }, [interactionRootRef, firePixelAtClient]);

  const columns = useMemo(
    () => Math.ceil(dimensions.width / pixelSize),
    [dimensions.width, pixelSize]
  );
  const rows = useMemo(
    () => Math.ceil(dimensions.height / pixelSize),
    [dimensions.height, pixelSize]
  );

  const useDelegatedPointer = Boolean(interactionRootRef);

  return (
    <div
      ref={containerRef}
      className={cn(
        'absolute inset-0 w-full h-full',
        useDelegatedPointer ? 'pointer-events-none' : 'pointer-events-auto',
        className
      )}
      onMouseMove={useDelegatedPointer ? undefined : handleMouseMove}
    >
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <PixelDot
              key={`${colIndex}-${rowIndex}`}
              id={`${trailId.current}-pixel-${colIndex}-${rowIndex}`}
              size={pixelSize}
              fadeDuration={fadeDuration}
              delay={delay}
              className={pixelClassName}
            />
          ))}
        </div>
      ))}
    </div>
  );
};

interface PixelDotProps {
  id: string;
  size: number;
  fadeDuration: number;
  delay: number;
  className?: string;
}

const PixelDot: React.FC<PixelDotProps> = React.memo(
  ({ id, size, fadeDuration, delay, className }) => {
    const controls = useAnimationControls();

    const animatePixel = useCallback(() => {
      controls.start({
        opacity: [1, 0],
        transition: { duration: fadeDuration / 1000, delay: delay / 1000 },
      });
    }, [controls, fadeDuration, delay]);

    const ref = useCallback(
      (node: HTMLDivElement | null) => {
        if (node) {
          (node as any).__animatePixel = animatePixel;
        }
      },
      [animatePixel]
    );

    return (
      <motion.div
        id={id}
        ref={ref}
        className={cn('pointer-events-none', className)}
        style={{ width: `${size}px`, height: `${size}px` }}
        initial={{ opacity: 0 }}
        animate={controls}
        exit={{ opacity: 0 }}
      />
    );
  }
);

PixelDot.displayName = 'PixelDot';
export { PixelTrail };
