import { useEffect, useRef } from 'react';
import { LoaderPinwheelIcon, type LoaderPinwheelIconHandle } from 'lucide-animated';

interface LoadingPinwheelProps {
  size?: number;
  className?: string;
  active: boolean;
}

/** Runs the lucide-animated pinwheel rotation while `active` (controlled ref). */
export function LoadingPinwheel({ size = 20, className, active }: LoadingPinwheelProps) {
  const ref = useRef<LoaderPinwheelIconHandle>(null);

  useEffect(() => {
    if (!active) {
      ref.current?.stopAnimation();
      return;
    }
    ref.current?.startAnimation();
    return () => ref.current?.stopAnimation();
  }, [active]);

  return <LoaderPinwheelIcon ref={ref} size={size} className={className} />;
}
