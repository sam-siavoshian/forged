import type { Phase } from '../types';

interface PhaseIndicatorProps {
  phase: Phase;
}

const CONFIG: Record<Phase, { label: string; dotColor: string; textColor: string }> = {
  idle: { label: 'Waiting', dotColor: 'bg-text-muted', textColor: 'text-text-muted' },
  rocket: { label: 'Playwright', dotColor: 'bg-accent', textColor: 'text-accent' },
  agent: { label: 'Agent', dotColor: 'bg-info', textColor: 'text-info' },
  complete: { label: 'Done', dotColor: 'bg-accent', textColor: 'text-accent' },
  error: { label: 'Error', dotColor: 'bg-red-400', textColor: 'text-red-400' },
  learning: { label: 'Learning', dotColor: 'bg-violet-400', textColor: 'text-violet-400' },
};

export function PhaseIndicator({ phase }: PhaseIndicatorProps) {
  const c = CONFIG[phase];
  const isActive = phase === 'rocket' || phase === 'agent';

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-mono ${c.textColor}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dotColor} ${isActive ? 'animate-pulse' : ''}`} />
      {c.label}
      {phase === 'agent' && (
        <span className="flex gap-px ml-0.5">
          <span className="w-1 h-1 rounded-full bg-info thinking-dot" />
          <span className="w-1 h-1 rounded-full bg-info thinking-dot thinking-dot-2" />
          <span className="w-1 h-1 rounded-full bg-info thinking-dot thinking-dot-3" />
        </span>
      )}
    </span>
  );
}
