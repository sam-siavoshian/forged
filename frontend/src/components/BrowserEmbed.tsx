import { CheckIcon } from 'lucide-animated';
import type { Phase } from '../types';
import { LoadingPinwheel } from './LoadingPinwheel';

interface BrowserEmbedProps {
  liveUrl: string | null;
  phase: Phase;
}

export function BrowserEmbed({ liveUrl, phase }: BrowserEmbedProps) {
  const active = phase === 'rocket' || phase === 'agent';
  const borderColor =
    phase === 'rocket' ? 'border-lime/12' :
    phase === 'agent' ? 'border-sky/12' :
    phase === 'complete' ? 'border-lime/8' :
    'border-border';

  return (
    <div className={`rounded-xl border ${borderColor} overflow-hidden transition-colors duration-700`} style={{ background: '#080808' }}>
      {/* Minimal chrome */}
      <div className="flex items-center gap-1.5 px-3 h-7 border-b border-border-subtle" style={{ background: '#0e0e0e' }}>
        <span className="w-[6px] h-[6px] rounded-full" style={{ background: '#222' }} />
        <span className="w-[6px] h-[6px] rounded-full" style={{ background: '#222' }} />
        <span className="w-[6px] h-[6px] rounded-full" style={{ background: '#222' }} />
        {liveUrl && (
          <span className="ml-2 text-[10px] font-mono text-text-muted truncate">{liveUrl}</span>
        )}
      </div>

      <div className="aspect-[16/10] relative">
        {liveUrl ? (
          <iframe
            src={liveUrl}
            sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
            allow="autoplay; clipboard-write"
            className="w-full h-full border-0"
            title="Browser view"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            {active ? (
              <LoadingPinwheel
                active
                size={20}
                className={phase === 'rocket' ? 'text-lime/40' : 'text-sky/40'}
              />
            ) : phase === 'complete' ? (
              <CheckIcon size={16} className="text-lime/25" />
            ) : (
              <div className="w-5 h-px" style={{ background: '#1a1a1a' }} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
