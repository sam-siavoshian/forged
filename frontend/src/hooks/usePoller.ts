import { useCallback, useEffect, useRef, useState } from 'react';
import { getStatus } from '../api';
import type { RunStatus } from '../types';

export function usePoller(sessionId: string | null, intervalMs = 500) {
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isPollingRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    isPollingRef.current = false;
  }, []);

  useEffect(() => {
    if (!sessionId) {
      stopPolling();
      return;
    }

    isPollingRef.current = true;
    setError(null);

    const poll = async () => {
      if (!isPollingRef.current) return;
      try {
        const s = await getStatus(sessionId);
        setStatus(s);
        if (s.status === 'complete' || s.status === 'error') {
          stopPolling();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Polling error');
        stopPolling();
      }
    };

    // Immediate first poll
    poll();
    intervalRef.current = setInterval(poll, intervalMs);

    return () => {
      stopPolling();
    };
  }, [sessionId, intervalMs, stopPolling]);

  return { status, error, stopPolling };
}
