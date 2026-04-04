import type { Step, Phase } from '../types';

interface StepTrackerProps {
  steps: Step[];
  phase: Phase;
  currentStep: string;
}

export function StepTracker({ steps, phase, currentStep }: StepTrackerProps) {
  const isActive = phase !== 'idle' && phase !== 'complete' && phase !== 'error';

  if (steps.length === 0 && phase === 'idle') {
    return null;
  }

  return (
    <div className="flex flex-col gap-px">
      {steps.map((step, i) => {
        const isRocket = step.type === 'playwright';

        return (
          <div
            key={step.id}
            className={`flex items-center gap-2.5 py-1.5 text-[13px] ${
              isRocket ? 'animate-step-rocket' : 'animate-step-agent'
            }`}
            style={{ animationDelay: isRocket ? `${i * 30}ms` : '0ms' }}
          >
            {/* Indicator line */}
            <div className={`w-0.5 h-4 rounded-full ${
              isRocket ? 'bg-accent' : 'bg-info/50'
            }`} />

            {/* Description */}
            <span className={`flex-1 truncate ${
              isRocket ? 'text-text' : 'text-text-secondary'
            }`}>
              {step.description}
            </span>

            {/* Duration */}
            {step.durationMs != null && (
              <span className={`font-mono text-xs tabular-nums ${
                isRocket ? 'text-accent/60' : 'text-text-muted'
              }`}>
                {step.durationMs < 1000
                  ? `${step.durationMs}ms`
                  : `${(step.durationMs / 1000).toFixed(1)}s`}
              </span>
            )}
          </div>
        );
      })}

      {/* Active step */}
      {isActive && currentStep && (
        <div className="flex items-center gap-2.5 py-1.5 text-[13px]">
          <div className={`w-0.5 h-4 rounded-full ${
            phase === 'rocket' ? 'bg-accent animate-pulse' : 'bg-info/50 animate-pulse'
          }`} />
          <span className={`flex-1 truncate ${
            phase === 'rocket' ? 'text-accent' : 'text-info'
          }`}>
            {currentStep}
          </span>
        </div>
      )}
    </div>
  );
}
