interface SessionStatsProps {
  elapsedMs: number;
  stepCount: number;
  modeUsed: 'rocket' | 'baseline_learn' | null;
  isComplete: boolean;
}

export function SessionStats({ elapsedMs, stepCount, modeUsed, isComplete }: SessionStatsProps) {
  const seconds = (elapsedMs / 1000).toFixed(1);

  return (
    <div
      className="flex items-center justify-between px-5 h-10 shrink-0"
      style={{
        borderTop: '1px solid var(--color-border)',
        background: 'rgba(0,0,0,0.2)',
        boxShadow: 'inset 0 1px 4px rgba(0,0,0,0.3)',
      }}
    >
      <div className="flex items-center gap-6 text-[11px] font-mono text-text-muted">
        <span>{seconds}s</span>
        <span>{stepCount} step{stepCount !== 1 ? 's' : ''}</span>
      </div>

      {modeUsed && (
        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{
              background: modeUsed === 'rocket' ? 'var(--color-lime)' : 'var(--color-amber)',
            }}
          />
          <span style={{ color: modeUsed === 'rocket' ? 'var(--color-lime)' : 'var(--color-amber)' }}>
            {modeUsed === 'rocket' ? 'rocket' : isComplete ? 'learned' : 'learning'}
          </span>
        </div>
      )}
    </div>
  );
}
