import { useCallback, useEffect, useRef, useState } from 'react';

export function useTimer() {
  const [elapsedMs, setElapsedMs] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const startTimeRef = useRef(0);
  const rafRef = useRef<number>(0);

  const tick = useCallback(() => {
    if (startTimeRef.current > 0) {
      setElapsedMs(Date.now() - startTimeRef.current);
      rafRef.current = requestAnimationFrame(tick);
    }
  }, []);

  const start = useCallback(() => {
    startTimeRef.current = Date.now();
    setElapsedMs(0);
    setIsRunning(true);
    rafRef.current = requestAnimationFrame(tick);
  }, [tick]);

  const stop = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
    setIsRunning(false);
  }, []);

  const reset = useCallback(() => {
    stop();
    setElapsedMs(0);
    startTimeRef.current = 0;
  }, [stop]);

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return { elapsedMs, isRunning, start, stop, reset };
}
