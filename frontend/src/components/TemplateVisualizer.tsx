import type { TemplateStep } from '../types';

interface TemplateVisualizerProps {
  steps: TemplateStep[];
  pattern: string;
  confidence: number;
}

const TYPE_COLOR: Record<TemplateStep['type'], string> = {
  fixed: 'bg-accent/10 text-accent border-accent/20',
  parameterized: 'bg-info/10 text-info border-info/20',
  dynamic: 'bg-warn/10 text-warn border-warn/20',
};

const TYPE_DOT: Record<TemplateStep['type'], string> = {
  fixed: 'bg-accent',
  parameterized: 'bg-info',
  dynamic: 'bg-warn',
};

export function TemplateVisualizer({ steps, pattern, confidence }: TemplateVisualizerProps) {
  const handoffIndex = steps.findIndex((s) => s.handoff);

  return (
    <div className="animate-fade-up">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-text-secondary font-mono">{pattern}</span>
        <span className={`font-mono text-sm font-semibold ${
          confidence >= 0.9 ? 'text-accent' : 'text-warn'
        }`}>
          {(confidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Steps */}
      <div className="space-y-1">
        {steps.map((step, i) => (
          <div key={step.id}>
            {i === handoffIndex && (
              <div className="flex items-center gap-3 my-3">
                <div className="flex-1 h-px bg-gradient-to-r from-accent/40 to-info/40" />
                <span className="text-[10px] uppercase tracking-[0.15em] text-text-muted">handoff</span>
                <div className="flex-1 h-px bg-gradient-to-r from-info/40 to-transparent" />
              </div>
            )}
            <div className={`flex items-center gap-2 px-3 py-2 rounded-md border text-[13px] ${TYPE_COLOR[step.type]}`}>
              <div className={`w-1 h-1 rounded-full ${TYPE_DOT[step.type]}`} />
              <span className="flex-1 truncate">{step.description}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-4">
        {(['fixed', 'parameterized', 'dynamic'] as const).map((type) => (
          <span key={type} className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.15em] text-text-muted">
            <span className={`w-1.5 h-1.5 rounded-full ${TYPE_DOT[type]}`} />
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}
