import type { Template } from '../types';

interface LearningHistoryProps {
  templates: Template[];
  onSelect?: (template: Template) => void;
  selectedId?: string;
}

export function LearningHistory({ templates, onSelect, selectedId }: LearningHistoryProps) {
  if (templates.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {templates.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onSelect?.(t)}
          className={`group flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs transition-all ${
            selectedId === t.id
              ? 'bg-surface border-accent/30 text-text'
              : 'bg-transparent border-border-subtle text-text-secondary hover:border-border hover:text-text'
          }`}
        >
          <span className="truncate max-w-[140px]">{t.domain}</span>
          <span className={`font-mono text-[10px] ${
            t.confidence >= 0.9 ? 'text-accent' : 'text-warn'
          }`}>
            {(t.confidence * 100).toFixed(0)}%
          </span>
        </button>
      ))}
    </div>
  );
}
