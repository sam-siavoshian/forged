import { useEffect, useRef } from 'react';
import type { Step, Phase } from '../types';

interface StepTrackerProps {
  steps: Step[];
  phase: Phase;
  currentStep: string;
}

export function StepTracker({ steps, phase, currentStep }: StepTrackerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isActive =
    phase === 'rocket' || phase === 'agent' || phase === 'learning';
  const lastStepDescription = steps[steps.length - 1]?.description;
  const showCurrentStep = Boolean(
    isActive &&
    currentStep &&
    currentStep !== lastStepDescription,
  );

  const lastStepId = steps[steps.length - 1]?.id;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [steps.length, lastStepId, currentStep, phase, showCurrentStep]);

  if (steps.length === 0 && !isActive) return null;

  return (
    <div className="flex flex-col gap-0.5">
      {steps.map((step, i) => {
        const fast = step.type === 'playwright';
        return (
          <div
            key={step.id}
            className={`flex items-center gap-2.5 py-[6px] px-1 text-[13px] leading-tight rounded-lg transition-colors ${
              fast ? 'anim-step-fast' : 'anim-step-slow'
            }`}
            style={fast ? { animationDelay: `${i * 25}ms` } : undefined}
          >
            <div
              className={`w-[3px] h-4 rounded-full flex-shrink-0 ${fast ? 'bg-lime' : 'bg-sky/40'}`}
              style={{
                boxShadow: fast ? '0 0 6px rgba(200,255,0,0.2)' : 'none',
              }}
            />
            <span className={`flex-1 truncate ${fast ? 'text-text' : 'text-text-dim'}`}>
              {step.description}
            </span>
            {step.durationMs != null && (
              <span className={`font-mono text-[11px] tabular-nums flex-shrink-0 ${
                fast ? 'text-lime/50' : 'text-text-muted'
              }`}>
                {step.durationMs < 1000 ? `${step.durationMs}ms` : `${(step.durationMs / 1000).toFixed(1)}s`}
              </span>
            )}
          </div>
        );
      })}

      {showCurrentStep && (
        <div className="flex items-center gap-2.5 py-[6px] px-1 text-[13px]">
          <div className={`w-[3px] h-4 rounded-full flex-shrink-0 ${
            phase === 'rocket' ? 'bg-lime dot-pulse' : 'bg-sky/40 dot-pulse'
          }`} />
          <span className={`flex-1 truncate ${
            phase === 'rocket' ? 'text-lime/80' : 'text-sky/80'
          }`}>
            {currentStep}
          </span>
        </div>
      )}

      <div ref={bottomRef} className="h-0 w-full shrink-0" aria-hidden />
    </div>
  );
}
