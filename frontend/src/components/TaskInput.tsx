import { useState } from 'react';

interface TaskInputProps {
  onRun: (task: string) => void;
  isRunning: boolean;
  onStop?: () => void;
}

export function TaskInput({ onRun, isRunning, onStop }: TaskInputProps) {
  const [task, setTask] = useState('Search for "best coffee shops in SF" on Google');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isRunning) {
      onStop?.();
      return;
    }
    if (!task.trim()) return;
    onRun(task.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl">
      <div className="relative flex items-center">
        <input
          type="text"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="What should the browser agent do?"
          disabled={isRunning}
          className="w-full h-12 pl-4 pr-28 bg-surface border border-border-subtle rounded-xl text-[15px] text-text placeholder-text-muted focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all font-display disabled:opacity-40"
        />
        <button
          type="submit"
          className={`absolute right-1.5 h-9 px-5 rounded-lg font-semibold text-sm tracking-wide transition-all ${
            isRunning
              ? 'bg-elevated text-text-secondary hover:bg-border'
              : 'bg-accent text-bg hover:brightness-110 active:scale-[0.97]'
          }`}
        >
          {isRunning ? 'Stop' : 'Race'}
        </button>
      </div>
    </form>
  );
}
