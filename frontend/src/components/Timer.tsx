interface TimerProps {
  elapsedMs: number;
  isComplete: boolean;
  variant: 'baseline' | 'rocket';
  /** Server-reported duration when the run finished; keeps UI in sync with /results */
  durationMs?: number;
}

export function Timer({ elapsedMs, isComplete, variant, durationMs }: TimerProps) {
  const ms =
    isComplete && durationMs != null && durationMs > 0 ? durationMs : elapsedMs;
  const seconds = ms / 1000;
  const formatted = seconds.toFixed(1);

  const color = isComplete
    ? variant === 'rocket' ? 'text-lime' : 'text-text-muted'
    : 'text-text';

  return (
    <span
      className={`font-mono tabular-nums font-medium text-xl ${color} transition-colors duration-500 px-2.5 py-1 rounded-xl`}
      style={{
        background: 'rgba(0,0,0,0.25)',
        boxShadow: 'inset 0 3px 8px rgba(0,0,0,0.35), inset 0 1px 2px rgba(0,0,0,0.2), inset 0 -1px 3px rgba(255,255,255,0.02), 0 1px 0 rgba(255,255,255,0.03)',
      }}
    >
      {formatted}<span className="text-[11px] text-text-muted ml-0.5">s</span>
    </span>
  );
}
