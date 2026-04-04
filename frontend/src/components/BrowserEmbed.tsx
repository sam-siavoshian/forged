import type { Phase } from '../types';

interface BrowserEmbedProps {
  liveUrl: string | null;
  phase: Phase;
}

export function BrowserEmbed({ liveUrl, phase }: BrowserEmbedProps) {
  const borderAccent =
    phase === 'rocket'
      ? 'border-accent/20'
      : phase === 'agent'
        ? 'border-info/20'
        : 'border-border-subtle';

  return (
    <div className={`rounded-lg border ${borderAccent} overflow-hidden bg-bg transition-colors duration-500`}>
      {/* Minimal browser bar */}
      <div className="flex items-center gap-1.5 px-3 py-2 bg-surface border-b border-border-subtle">
        <div className="w-2 h-2 rounded-full bg-border" />
        <div className="w-2 h-2 rounded-full bg-border" />
        <div className="w-2 h-2 rounded-full bg-border" />
        {liveUrl && (
          <div className="ml-2 flex-1 text-[11px] font-mono text-text-muted truncate">
            {liveUrl}
          </div>
        )}
      </div>

      {/* Viewport */}
      <div className="aspect-[16/10] relative bg-bg">
        {liveUrl ? (
          <iframe
            src={liveUrl}
            sandbox="allow-same-origin allow-scripts"
            className="w-full h-full border-0"
            title="Browser view"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            {phase === 'idle' ? (
              <div className="text-text-muted/30 text-sm font-mono">—</div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <div className={`w-8 h-8 rounded-full border-2 border-t-transparent animate-spin ${
                  phase === 'rocket' ? 'border-accent/40' : 'border-info/40'
                }`} />
                <span className="text-[11px] font-mono text-text-muted">
                  {phase === 'complete' ? 'Complete' : 'Running...'}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
