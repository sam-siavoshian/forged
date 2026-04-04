import { useEffect, useState } from 'react';

interface ComparisonCardProps {
  baselineDurationMs: number;
  rocketDurationMs: number;
  onReset: () => void;
}

export function ComparisonCard({ baselineDurationMs, rocketDurationMs, onReset }: ComparisonCardProps) {
  const speedup = baselineDurationMs / rocketDurationMs;
  const timeSaved = (baselineDurationMs - rocketDurationMs) / 1000;
  const baselineSec = (baselineDurationMs / 1000).toFixed(1);
  const rocketSec = (rocketDurationMs / 1000).toFixed(1);
  const barRatio = rocketDurationMs / baselineDurationMs;

  // Stagger entrance
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const t1 = setTimeout(() => setStage(1), 200);
    const t2 = setTimeout(() => setStage(2), 600);
    const t3 = setTimeout(() => setStage(3), 1000);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-lg mx-4 animate-scale-in">
        {/* The number */}
        <div className="text-center mb-10">
          {stage >= 1 && (
            <div className="animate-number-pop">
              <span className="text-8xl font-display font-extrabold gradient-text tracking-tight">
                {speedup.toFixed(1)}x
              </span>
              <div className="text-text-secondary text-lg mt-2 font-display">
                faster
              </div>
            </div>
          )}
        </div>

        {/* Comparison bars */}
        {stage >= 2 && (
          <div className="space-y-3 animate-fade-up">
            {/* Baseline bar */}
            <div className="flex items-center gap-3">
              <span className="w-20 text-right text-sm text-text-muted font-mono">{baselineSec}s</span>
              <div className="flex-1 h-8 bg-surface rounded-md overflow-hidden">
                <div
                  className="h-full bg-warn/20 rounded-md"
                  style={{ width: '100%', animation: 'bar-fill 0.8s ease-out both' }}
                />
              </div>
              <span className="w-20 text-xs text-text-muted">Baseline</span>
            </div>

            {/* Rocket bar */}
            <div className="flex items-center gap-3">
              <span className="w-20 text-right text-sm text-accent font-mono font-semibold">{rocketSec}s</span>
              <div className="flex-1 h-8 bg-surface rounded-md overflow-hidden">
                <div
                  className="h-full bg-accent/30 rounded-md glow-green"
                  style={{
                    width: `${barRatio * 100}%`,
                    animation: 'bar-fill 0.8s ease-out both',
                    animationDelay: '0.2s',
                  }}
                />
              </div>
              <span className="w-20 text-xs text-accent">Boosted</span>
            </div>
          </div>
        )}

        {/* Summary + action */}
        {stage >= 3 && (
          <div className="mt-10 text-center animate-fade-up">
            <p className="text-text-secondary text-sm">
              Saved <span className="text-accent font-semibold font-mono">{timeSaved.toFixed(1)}s</span> by
              replaying learned steps with Playwright
            </p>
            <button
              onClick={onReset}
              className="mt-6 px-6 py-2.5 bg-surface border border-border rounded-lg text-sm text-text hover:bg-elevated transition-colors"
            >
              Run another task
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
