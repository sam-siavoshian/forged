import { useState } from 'react';
import type { Step } from '../../types';

const ACTION_ICONS: Record<string, string> = {
  navigate: 'M3 12a9 9 0 1 0 18 0a9 9 0 0 0-18 0M3.6 9h16.8M3.6 15h16.8M12 3a17 17 0 0 1 0 18M12 3a17 17 0 0 0 0 18',
  click: 'M9 9l5 12 1.8-5.2L21 14 9 9Z',
  fill: 'M17 10H3M21 6H3M21 14H3M17 18H3',
  press: 'M12 2v6l3.5 3.5M6.3 20.7l3.5-3.5',
  extract: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8ZM14 2v6h6M16 13H8M16 17H8M10 9H8',
  search_web: 'M21 21l-4.35-4.35M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z',
  scroll: 'M12 5v14M5 12l7-7 7 7',
  done: 'M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4L12 14.01l-3-3',
  template_match: 'M13 2L3 14h9l-1 8 10-12h-9l1-8',
  agent_action: 'M12 8v4l3 3',
};

interface ActionCardProps {
  step: Step;
  isLast?: boolean;
  isRunning?: boolean;
}

export function ActionCard({ step, isLast, isRunning }: ActionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const actionType = step.action_type || 'agent_action';
  const iconPath = ACTION_ICONS[actionType] || ACTION_ICONS.agent_action;
  const isTemplateMatch = actionType === 'template_match';
  const isDone = actionType === 'done';
  const isLastAndRunning = isLast && isRunning;

  const duration = step.durationMs != null
    ? step.durationMs < 1000 ? `${Math.round(step.durationMs)}ms` : `${(step.durationMs / 1000).toFixed(1)}s`
    : null;

  // Color based on step type
  const accentColor = step.type === 'playwright' ? 'var(--color-lime)' : 'var(--color-sky)';
  const dotColor = isTemplateMatch
    ? (step.details?.mode === 'rocket' ? 'var(--color-lime)' : 'var(--color-amber)')
    : isDone ? 'var(--color-lime)' : accentColor;

  return (
    <div
      className="group relative cursor-pointer transition-all duration-150"
      onClick={() => step.details && setExpanded(!expanded)}
      style={{ animation: 'fade-up 0.3s cubic-bezier(0.16,1,0.3,1) both' }}
    >
      <div className="flex items-start gap-3.5 px-4 py-3 rounded-xl mx-2
                       hover:bg-white/[0.02] transition-colors duration-150">
        {/* Timeline dot */}
        <div className="relative shrink-0 mt-1">
          <div
            className={`w-[7px] h-[7px] rounded-full ${isLastAndRunning ? 'dot-pulse' : ''}`}
            style={{ background: dotColor }}
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Title row */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              {/* Icon */}
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={dotColor}
                   strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                   className="shrink-0 opacity-60">
                <path d={iconPath} />
              </svg>
              {/* Description */}
              <span className="text-[13px] text-text/90 leading-snug truncate">
                {step.description.replace(/^Agent:\s*/, '')}
              </span>
            </div>

            {/* Duration + badge */}
            <div className="flex items-center gap-2 shrink-0">
              {duration && (
                <span className="text-[10px] font-mono text-text-muted">{duration}</span>
              )}
              <span
                className="text-[9px] font-mono px-1.5 py-[2px] rounded-md uppercase tracking-wider"
                style={{
                  background: step.type === 'playwright' ? 'rgba(200,255,0,0.08)' : 'rgba(56,189,248,0.08)',
                  color: step.type === 'playwright' ? 'var(--color-lime)' : 'var(--color-sky)',
                }}
              >
                {step.type === 'playwright' ? 'pw' : 'ai'}
              </span>
            </div>
          </div>

          {/* Expanded details */}
          {expanded && step.details && (
            <div className="mt-2.5 ml-[21px] space-y-1.5 pb-1">
              {Object.entries(step.details).map(([k, v]) => (
                <div key={k} className="flex gap-2 text-[11px]">
                  <span className="text-text-muted shrink-0 font-mono">{k}</span>
                  <span className="text-text-dim truncate">{String(v)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
