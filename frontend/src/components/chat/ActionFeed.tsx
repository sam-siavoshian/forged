import { useEffect, useRef } from 'react';
import { ActionCard } from './ActionCard';
import { ShiningText } from '../ui/shining-text';
import type { Step } from '../../types';

interface ActionFeedProps {
  steps: Step[];
  isRunning: boolean;
  agentResult?: string | null;
  isComplete?: boolean;
}

export function ActionFeed({ steps, isRunning, agentResult, isComplete }: ActionFeedProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps.length, agentResult]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto py-3">
        {steps.length === 0 && isRunning && (
          <div className="flex items-center gap-3 px-6 py-4"
               style={{ animation: 'fade-in 0.3s ease both' }}>
            <div className="w-2 h-2 rounded-full bg-sky dot-pulse" />
            <ShiningText text="Starting agent..." className="text-[12px]" />
          </div>
        )}

        {/* Timeline */}
        <div className="relative">
          {/* Vertical connector line */}
          {steps.length > 1 && (
            <div
              className="absolute left-[26px] top-6 bottom-6 w-px"
              style={{ background: 'linear-gradient(to bottom, var(--color-border), transparent)' }}
            />
          )}

          {steps.map((step, i) => (
            <ActionCard
              key={step.id}
              step={step}
              isLast={i === steps.length - 1}
              isRunning={isRunning}
            />
          ))}
        </div>

        {/* Thinking indicator */}
        {isRunning && steps.length > 0 && (
          <div className="flex items-center gap-3 px-6 py-3 ml-[6px]">
            <div className="w-[7px] h-[7px] rounded-full bg-sky dot-pulse shrink-0" />
            <ShiningText text="Thinking..." className="text-[12px]" />
          </div>
        )}

        {/* Agent result card */}
        {agentResult && isComplete && (
          <div className="mx-4 mt-3 mb-2" style={{ animation: 'fade-up 0.4s cubic-bezier(0.16,1,0.3,1) both' }}>
            <div
              className="rounded-2xl px-5 py-4"
              style={{
                background: 'rgba(200,255,0,0.03)',
                border: '1px solid rgba(200,255,0,0.1)',
                boxShadow: `
                  inset 0 4px 12px rgba(0,0,0,0.3),
                  inset 0 1px 3px rgba(0,0,0,0.2),
                  inset 0 -1px 3px rgba(200,255,0,0.02),
                  0 0 20px rgba(200,255,0,0.03)
                `,
              }}
            >
              {/* Header */}
              <div className="flex items-center gap-2 mb-3">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                     stroke="var(--color-lime)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <path d="M22 4L12 14.01l-3-3" />
                </svg>
                <span className="text-[11px] font-mono uppercase tracking-wider text-lime">
                  Result
                </span>
              </div>
              {/* Content */}
              <div className="text-[13px] text-text/90 leading-[1.7] whitespace-pre-wrap break-words">
                {agentResult}
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
