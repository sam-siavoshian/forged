interface TimerProps {
  elapsedMs: number;
  isComplete: boolean;
  variant: 'baseline' | 'rocket';
}

export function Timer({ elapsedMs, isComplete, variant }: TimerProps) {
  const seconds = elapsedMs / 1000;
  const formatted = seconds < 100 ? seconds.toFixed(1) : Math.round(seconds).toString();

  const color = isComplete
    ? variant === 'rocket'
      ? 'text-accent'
      : 'text-text-secondary'
    : 'text-text';

  return (
    <div className={`font-mono tabular-nums font-bold ${color} transition-colors duration-300`}>
      <span className="text-3xl">{formatted}</span>
      <span className="text-lg text-text-muted ml-0.5">s</span>
    </div>
  );
}
