import { useEffect, useRef } from 'react';
import { ActionCard } from './ActionCard';
import { ShiningText } from '../ui/shining-text';
import type { Step } from '../../types';

interface ActionFeedProps {
  steps: Step[];
  isRunning: boolean;
}

export function ActionFeed({ steps, isRunning }: ActionFeedProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps.length]);

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

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
