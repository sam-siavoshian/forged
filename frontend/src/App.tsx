import { useCallback, useEffect, useState } from 'react';
import { TaskInput } from './components/TaskInput';
import { BrowserEmbed } from './components/BrowserEmbed';
import { Timer } from './components/Timer';
import { StepTracker } from './components/StepTracker';
import { PhaseIndicator } from './components/PhaseIndicator';
import { ComparisonCard } from './components/ComparisonCard';
import { TemplateVisualizer } from './components/TemplateVisualizer';
import { LearningHistory } from './components/LearningHistory';
import { usePoller } from './hooks/usePoller';
import { useTimer } from './hooks/useTimer';
import { startCompare, getTemplates } from './api';
import type { Template, Phase } from './types';

type AppState = 'idle' | 'racing' | 'results';

function App() {
  const [appState, setAppState] = useState<AppState>('idle');
  const [currentTask, setCurrentTask] = useState('');

  // Sessions
  const [baselineSessionId, setBaselineSessionId] = useState<string | null>(null);
  const [rocketSessionId, setRocketSessionId] = useState<string | null>(null);

  // Templates
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);

  // Pollers
  const { status: baselineStatus } = usePoller(baselineSessionId);
  const { status: rocketStatus } = usePoller(rocketSessionId);

  // Timers
  const baselineTimer = useTimer();
  const rocketTimer = useTimer();

  // Load templates
  useEffect(() => {
    getTemplates().then(setTemplates).catch(() => {});
  }, []);

  // Stop timers when complete
  useEffect(() => {
    if (baselineStatus?.status === 'complete' || baselineStatus?.status === 'error') {
      baselineTimer.stop();
    }
  }, [baselineStatus?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (rocketStatus?.status === 'complete' || rocketStatus?.status === 'error') {
      rocketTimer.stop();
    }
  }, [rocketStatus?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Both done → show results
  useEffect(() => {
    if (baselineStatus?.status === 'complete' && rocketStatus?.status === 'complete') {
      setTimeout(() => setAppState('results'), 800);
    }
  }, [baselineStatus?.status, rocketStatus?.status]);

  const handleRun = useCallback(async (task: string) => {
    setCurrentTask(task);
    setBaselineSessionId(null);
    setRocketSessionId(null);
    setSelectedTemplate(null);
    baselineTimer.reset();
    rocketTimer.reset();
    setAppState('racing');

    try {
      const { baseline_session_id, rocket_session_id } = await startCompare(task);
      setBaselineSessionId(baseline_session_id);
      setRocketSessionId(rocket_session_id);
      baselineTimer.start();
      rocketTimer.start();
    } catch (err) {
      console.error('Failed to start race:', err);
      setAppState('idle');
    }
  }, [baselineTimer, rocketTimer]);

  const handleReset = useCallback(() => {
    setBaselineSessionId(null);
    setRocketSessionId(null);
    baselineTimer.reset();
    rocketTimer.reset();
    setAppState('idle');
  }, [baselineTimer, rocketTimer]);

  const baselinePhase: Phase = baselineStatus?.phase ?? 'idle';
  const rocketPhase: Phase = rocketStatus?.phase ?? 'idle';
  const isRunning = appState === 'racing';

  // Live speedup
  const liveSpeedup =
    baselineTimer.elapsedMs > 1000 && rocketTimer.elapsedMs > 100
      ? baselineTimer.elapsedMs / rocketTimer.elapsedMs
      : null;

  return (
    <div className="h-screen flex flex-col relative overflow-hidden">
      {/* ── Subtle background gradient ── */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-accent/[0.02] rounded-full blur-[120px]" />
      </div>

      {/* ── Header ── */}
      <header className="relative z-10 flex items-center justify-between px-6 h-16 border-b border-border-subtle">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center text-sm">
            ⚡
          </div>
          <span className="text-[15px] font-semibold tracking-tight">Rocket Booster</span>
        </div>

        <div className="flex-1 flex justify-center">
          <TaskInput
            onRun={handleRun}
            isRunning={isRunning}
            onStop={handleReset}
          />
        </div>

        {/* Live indicator */}
        <div className="w-32 flex justify-end">
          {isRunning && (
            <span className="flex items-center gap-1.5 text-xs font-mono text-accent animate-fade-in">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              Live
            </span>
          )}
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="flex-1 relative z-10 flex flex-col overflow-hidden">

        {/* Idle state — hero */}
        {appState === 'idle' && (
          <div className="flex-1 flex flex-col items-center justify-center px-6 animate-fade-in">
            <div className="text-center mb-12">
              <h2 className="text-4xl font-bold tracking-tight mb-3">
                Make browser agents <span className="gradient-text">5x faster</span>
              </h2>
              <p className="text-text-secondary text-lg max-w-md mx-auto leading-relaxed">
                Learn from past runs. Replay known steps with Playwright.
                Let the agent handle the rest.
              </p>
            </div>

            {/* How it works */}
            <div className="flex items-center gap-8 mb-12">
              {[
                { step: '1', label: 'Run a task', desc: 'The agent completes it normally' },
                { step: '2', label: 'Learn the pattern', desc: 'We extract reusable steps' },
                { step: '3', label: 'Race it', desc: 'Watch Playwright blast through' },
              ].map((item, i) => (
                <div
                  key={item.step}
                  className="flex items-start gap-3 animate-fade-up"
                  style={{ animationDelay: `${i * 100}ms` }}
                >
                  <span className="w-6 h-6 rounded-full bg-surface border border-border flex items-center justify-center text-[11px] font-mono text-text-muted flex-shrink-0 mt-0.5">
                    {item.step}
                  </span>
                  <div>
                    <div className="text-sm font-medium text-text">{item.label}</div>
                    <div className="text-xs text-text-muted mt-0.5">{item.desc}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Templates as pills */}
            {templates.length > 0 && (
              <div className="animate-fade-up" style={{ animationDelay: '300ms' }}>
                <div className="text-[10px] uppercase tracking-[0.2em] text-text-muted mb-3 text-center">
                  Learned templates
                </div>
                <LearningHistory
                  templates={templates}
                  onSelect={setSelectedTemplate}
                  selectedId={selectedTemplate?.id}
                />
              </div>
            )}

            {/* Template detail */}
            {selectedTemplate && (
              <div className="mt-6 w-full max-w-lg">
                <TemplateVisualizer
                  steps={selectedTemplate.steps}
                  pattern={selectedTemplate.pattern}
                  confidence={selectedTemplate.confidence}
                />
              </div>
            )}
          </div>
        )}

        {/* Racing state — split view */}
        {appState === 'racing' && (
          <div className="flex-1 flex overflow-hidden animate-fade-in">

            {/* Left: Baseline */}
            <div className="flex-1 flex flex-col p-5 overflow-hidden">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-text-secondary">Baseline</span>
                  <PhaseIndicator phase={baselinePhase} />
                </div>
                <Timer
                  elapsedMs={baselineTimer.elapsedMs}
                  isComplete={baselineStatus?.status === 'complete'}
                  variant="baseline"
                />
              </div>

              <BrowserEmbed liveUrl={baselineStatus?.live_url ?? null} phase={baselinePhase} />

              <div className="mt-3 flex-1 overflow-y-auto">
                <StepTracker
                  steps={baselineStatus?.steps ?? []}
                  phase={baselinePhase}
                  currentStep={baselineStatus?.current_step ?? ''}
                />
              </div>
            </div>

            {/* Center divider with live speedup */}
            <div className="w-px bg-border-subtle relative flex-shrink-0">
              {liveSpeedup && liveSpeedup > 1 && (
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                  <div className="glass border border-accent/20 rounded-full px-4 py-2 glow-green animate-scale-in">
                    <span className="font-mono text-lg font-bold text-accent">
                      {liveSpeedup.toFixed(1)}x
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Right: Rocket */}
            <div className="flex-1 flex flex-col p-5 overflow-hidden">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-accent">Rocket Booster</span>
                  <PhaseIndicator phase={rocketPhase} />
                </div>
                <Timer
                  elapsedMs={rocketTimer.elapsedMs}
                  isComplete={rocketStatus?.status === 'complete'}
                  variant="rocket"
                />
              </div>

              <BrowserEmbed liveUrl={rocketStatus?.live_url ?? null} phase={rocketPhase} />

              <div className="mt-3 flex-1 overflow-y-auto">
                <StepTracker
                  steps={rocketStatus?.steps ?? []}
                  phase={rocketPhase}
                  currentStep={rocketStatus?.current_step ?? ''}
                />
              </div>
            </div>
          </div>
        )}

        {/* Task context bar during race */}
        {appState === 'racing' && (
          <div className="border-t border-border-subtle px-6 py-2.5 flex items-center justify-between bg-surface/50">
            <span className="text-xs text-text-muted font-mono truncate max-w-lg">
              {currentTask}
            </span>
            <span className="text-xs text-text-muted font-mono">
              {(baselineStatus?.steps.length ?? 0) + (rocketStatus?.steps.length ?? 0)} total steps
            </span>
          </div>
        )}
      </main>

      {/* ── Results overlay ── */}
      {appState === 'results' && baselineStatus && rocketStatus && (
        <ComparisonCard
          baselineDurationMs={baselineStatus.duration_ms}
          rocketDurationMs={rocketStatus.duration_ms}
          onReset={handleReset}
        />
      )}
    </div>
  );
}

export default App;
