import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { BrainIcon, ZapIcon } from 'lucide-animated';
import { AppSidebar, MobileTopBar } from './components/AppSidebar';
import { TaskInput } from './components/TaskInput';
import { BrowserEmbed } from './components/BrowserEmbed';
import { Timer } from './components/Timer';
import { StepTracker } from './components/StepTracker';
import { PhaseIndicator } from './components/PhaseIndicator';
import { ComparisonCard } from './components/ComparisonCard';
import { TemplateSearchCard } from './components/TemplateSearchCard';
import { ChatPage } from './pages/ChatPage';
import { BenchmarksPage } from './components/BenchmarksPage';
import { DocsLayout } from './pages/docs/DocsLayout';
import { usePoller } from './hooks/usePoller';
import { useTimer } from './hooks/useTimer';
import { startCompare, startLearn, getTemplates } from './api';
import type { Template, Phase } from './types';

type View = 'chat' | 'chat_session' | 'learning' | 'racing' | 'results' | 'benchmarks';

function pathToView(pathname: string): View {
  const p = pathname.replace(/\/+$/, '') || '/';
  if (p.startsWith('/learn/')) return 'chat_session';
  if (p === '/learn') return 'chat';
  if (p.startsWith('/chat/')) return 'chat_session';
  if (p === '/rl/learn') return 'learning';
  if (p === '/rl/race') return 'racing';
  if (p === '/rl/results') return 'results';
  if (p === '/benchmarks') return 'benchmarks';
  if (p === '/race') return 'racing';
  if (p === '/results') return 'results';
  return 'chat';
}

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const view = useMemo(() => pathToView(location.pathname), [location.pathname]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [learnStarting, setLearnStarting] = useState(false);
  const [raceStarting, setRaceStarting] = useState(false);
  const [currentTask, setCurrentTask] = useState('');
  const [baselineId, setBaselineId] = useState<string | null>(null);
  const [rocketId, setRocketId] = useState<string | null>(null);
  const [learnId, setLearnId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [totalTimeSavedMs, setTotalTimeSavedMs] = useState(0);
  const [raceCount, setRaceCount] = useState(0);

  const { status: baseStatus } = usePoller(baselineId);
  const { status: rocketStatus } = usePoller(rocketId);
  const { status: learnStatus } = usePoller(learnId);
  const baseTimer = useTimer();
  const rocketTimer = useTimer();
  const learnTimer = useTimer();

  useEffect(() => { getTemplates().then(setTemplates).catch(() => {}); }, []);

  useEffect(() => {
    if (baseStatus?.status === 'complete' || baseStatus?.status === 'error') baseTimer.stop();
  }, [baseStatus?.status]);
  useEffect(() => {
    if (rocketStatus?.status === 'complete' || rocketStatus?.status === 'error') rocketTimer.stop();
  }, [rocketStatus?.status]);
  useEffect(() => {
    if (
      learnStatus?.agent_complete ||
      learnStatus?.status === 'complete' ||
      learnStatus?.status === 'error'
    ) learnTimer.stop();
  }, [learnStatus?.agent_complete, learnStatus?.status]);

  useEffect(() => {
    const p = location.pathname.replace(/\/+$/, '') || '/';
    const chatLegacy = p.match(/^\/chat\/(.+)$/);
    if (chatLegacy) {
      navigate(`/learn/${chatLegacy[1]}`, { replace: true });
      return;
    }
    if (p === '/chat') {
      navigate('/learn', { replace: true });
    }
  }, [location.pathname, navigate]);

  useEffect(() => {
    const p = location.pathname.replace(/\/+$/, '') || '/';
    const allowed = ['/', '/learn', '/race', '/results', '/rl/learn', '/rl/race', '/rl/results', '/benchmarks'];
    if (!allowed.includes(p) && !p.startsWith('/chat/') && !p.startsWith('/learn/') && !p.startsWith('/docs')) {
      navigate('/learn', { replace: true });
    }
  }, [location.pathname, navigate]);

  const [searchingTask, setSearchingTask] = useState<string | null>(null);

  const launch = useCallback((task: string) => {
    setCurrentTask(task);
    setSearchingTask(task);
  }, []);

  const startRace = useCallback(async () => {
    const task = searchingTask || currentTask;
    setSearchingTask(null);
    setBaselineId(null);
    setRocketId(null);
    baseTimer.reset();
    rocketTimer.reset();
    setRaceStarting(true);
    navigate('/race');
    try {
      const { baseline_session_id, rocket_session_id } = await startCompare(task);
      setBaselineId(baseline_session_id);
      setRocketId(rocket_session_id);
      baseTimer.start();
      rocketTimer.start();
    } catch {
      navigate('/learn');
    } finally {
      setRaceStarting(false);
    }
  }, [searchingTask, currentTask, baseTimer, rocketTimer, navigate]);

  const learn = useCallback(async (task: string) => {
    setCurrentTask(task);
    setSearchingTask(null);
    setLearnId(null);
    learnTimer.reset();
    setLearnStarting(true);
    navigate('/rl/learn');
    try {
      const sessionId = await startLearn(task);
      setLearnId(sessionId);
      learnTimer.start();
    } catch {
      navigate('/learn');
    } finally {
      setLearnStarting(false);
    }
  }, [learnTimer, navigate]);

  const reset = useCallback(() => {
    setSearchingTask(null);
    setBaselineId(null);
    setRocketId(null);
    setLearnId(null);
    baseTimer.reset();
    rocketTimer.reset();
    learnTimer.reset();
    navigate('/learn');
    getTemplates().then(setTemplates).catch(() => {});
  }, [baseTimer, rocketTimer, learnTimer, navigate]);

  const basePh: Phase = baseStatus?.phase ?? 'idle';
  const rocketPh: Phase = rocketStatus?.phase ?? 'idle';
  const learnPh: Phase = learnStatus?.phase ?? 'idle';
  const isRunning = view === 'racing' || view === 'learning';
  const liveSpeedup = baseTimer.elapsedMs > 2000 && rocketTimer.elapsedMs > 200
    ? baseTimer.elapsedMs / rocketTimer.elapsedMs : null;
  const isChatView = view === 'chat' || view === 'chat_session';
  const raceBothComplete = Boolean(
    view === 'racing' &&
      baselineId &&
      rocketId &&
      baseStatus?.status === 'complete' &&
      rocketStatus?.status === 'complete',
  );

  // Accumulate time saved when a race completes
  const lastAccumulatedRace = useRef<string | null>(null);
  useEffect(() => {
    if (
      raceBothComplete &&
      baseStatus &&
      rocketStatus &&
      baseStatus.duration_ms > rocketStatus.duration_ms &&
      lastAccumulatedRace.current !== baselineId
    ) {
      lastAccumulatedRace.current = baselineId;
      setTotalTimeSavedMs((prev) => prev + (baseStatus.duration_ms - rocketStatus.duration_ms));
      setRaceCount((prev) => prev + 1);
    }
  }, [raceBothComplete, baseStatus, rocketStatus, baselineId]);

  const isDocsView = location.pathname.startsWith('/docs');
  if (isDocsView) {
    return (
      <div className="h-full min-h-0 flex flex-col bg-bg">
        <DocsLayout />
      </div>
    );
  }

  const pathNorm = location.pathname.replace(/\/+$/, '') || '/';
  if (pathNorm === '/') {
    return <Navigate to="/learn" replace />;
  }

  return (
    <div className="h-full min-h-0 flex flex-col md:flex-row bg-bg">
      {/* Sidebar */}
      <AppSidebar
        templates={templates}
        sidebarOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        collapsed={sidebarCollapsed}
        onCollapse={setSidebarCollapsed}
      />

      {/* Main content area */}
      <div className="flex-1 min-w-0 min-h-0 flex flex-col relative overflow-hidden">
        {/* Mobile top bar */}
        <MobileTopBar onToggle={() => setSidebarOpen(!sidebarOpen)} />

        {/* Ambient glow */}
        <div className="fixed inset-0 pointer-events-none z-0">
          <div className="absolute top-[-300px] left-1/2 -translate-x-1/2 w-[700px] h-[700px] rounded-full"
            style={{ background: 'radial-gradient(circle, rgba(200,255,0,0.02) 0%, transparent 65%)' }} />
        </div>

        {/* ═══ CHAT (browser agent — idle + session at /learn) ═══ */}
        {isChatView && (
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden relative z-10">
            <ChatPage />
          </div>
        )}

        {/* ═══ LEARNING VIEW ═══ */}
        {view === 'learning' && !learnId && !learnStarting && (
          <div className="flex-1 flex flex-col relative z-10 overflow-y-auto">
            <div className="flex flex-col items-center px-6 pt-12 pb-20">
              {/* Header */}
              <div className="text-center mb-8 anim-fade-up">
                <div className="w-12 h-12 rounded-2xl bg-amber-400/10 flex items-center justify-center mx-auto mb-5">
                  <BrainIcon size={22} className="text-amber-400" />
                </div>
                <h2 className="text-[28px] font-serif italic text-text mb-3">What do you want to learn?</h2>
                <p className="text-[14px] text-text-dim leading-relaxed max-w-[420px] mx-auto">
                  Describe a site or flow to explore—the agent learns by doing: it records each step and turns the
                  whole path into a playbook you can run again on similar pages.
                </p>
              </div>

              {/* Learn-only input */}
              <div className="w-full max-w-[520px] mb-12 anim-fade-up" style={{ animationDelay: '60ms' }}>
                <TaskInput onRun={(task) => learn(task)} isRunning={false} />
              </div>

              {/* Learned templates */}
              {templates.length > 0 && (
                <div className="w-full max-w-2xl anim-fade-up" style={{ animationDelay: '120ms' }}>
                  <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-muted mb-4 text-center">
                    {templates.length} learning{templates.length !== 1 ? 's' : ''} captured
                  </p>
                  <div className="flex flex-col gap-2">
                    {templates.map((t) => (
                      <div
                        key={t.id}
                        className="saas-card p-4 flex items-start gap-4"
                      >
                        <div className="w-9 h-9 rounded-xl bg-surface flex items-center justify-center shrink-0 border border-border">
                          <img
                            src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(t.domain)}&sz=32`}
                            alt=""
                            width={18}
                            height={18}
                            className="rounded-sm"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="mb-1">
                            <span className="text-[13px] font-medium text-text truncate block">{t.domain}</span>
                          </div>
                          <p className="text-[12px] text-text-dim truncate">{t.pattern}</p>
                          {t.steps && t.steps.length > 0 && (
                            <div className="flex items-center gap-1.5 mt-2">
                              {t.steps.slice(0, 8).map((step) => (
                                <div
                                  key={step.id}
                                  className={`w-1.5 h-1.5 rounded-full ${
                                    step.type === 'fixed' ? 'bg-lime/60' :
                                    step.type === 'parameterized' ? 'bg-amber-400/60' :
                                    'bg-sky-400/60'
                                  }`}
                                  title={`${step.type}: ${step.description}`}
                                />
                              ))}
                              {t.steps.length > 8 && (
                                <span className="text-[9px] text-text-muted">+{t.steps.length - 8}</span>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="text-[10px] text-text-muted font-mono shrink-0">
                          {t.uses} run{t.uses !== 1 ? 's' : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {templates.length === 0 && (
                <div className="text-center anim-fade-up" style={{ animationDelay: '120ms' }}>
                  <div className="saas-inset-sm px-8 py-6 rounded-2xl">
                    <p className="text-[13px] text-text-dim mb-1">Nothing captured yet</p>
                    <p className="text-[12px] text-text-muted">
                      Describe something you want to learn above—the first run becomes your first saved playbook.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        {view === 'learning' && (learnId || learnStarting) && (
          <div className="flex-1 flex flex-col min-h-0 relative z-10 anim-fade-in">
            <header className="flex-shrink-0 flex items-center gap-4 px-5 h-12 border-b border-border-subtle bg-surface/30 backdrop-blur-sm">
              <div className="flex items-center gap-2.5 flex-shrink-0">
                <div className="w-[7px] h-[7px] rounded-full bg-amber-400 dot-pulse" />
                <span className="text-[13px] font-medium text-amber-400">Learning Mode</span>
              </div>
              <div className="flex-1 text-[12px] text-text-muted truncate font-mono min-w-0">{currentTask}</div>
              <Timer elapsedMs={learnTimer.elapsedMs} isComplete={learnStatus?.status === 'complete'} variant="baseline" />
            </header>
            <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
              <div className="flex flex-col items-center p-6 pb-10">
                <div className="w-full max-w-3xl">
                  <div className="flex items-center gap-2.5 mb-4">
                    <PhaseIndicator phase={learnPh} />
                    <span className="text-[13px] text-text-dim">
                      {learnPh === 'agent' && 'Agent running the task...'}
                      {learnPh === 'learning' && 'Extracting template from trace...'}
                      {learnPh === 'complete' && 'Template learned!'}
                      {learnPh === 'error' && 'Learning failed'}
                      {learnPh === 'idle' && 'Starting...'}
                    </span>
                  </div>
                  <BrowserEmbed liveUrl={learnStatus?.live_url ?? null} phase={learnPh === 'learning' ? 'agent' : learnPh} />
                  <div className="mt-5">
                    <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-text-muted mb-2.5">Activity</p>
                    <div className="saas-inset px-4 py-3 max-h-[min(42vh,400px)] overflow-y-auto">
                      <StepTracker steps={learnStatus?.steps ?? []} phase={learnPh} currentStep={learnStatus?.current_step ?? ''} />
                    </div>
                  </div>
                  {learnStatus?.status === 'complete' && (
                    <div className="mt-8 saas-card p-6 text-center anim-scale-up" style={{ borderColor: 'rgba(200,255,0,0.15)', background: 'rgba(200,255,0,0.03)' }}>
                      <div className="text-lime text-lg font-semibold mb-1.5">Template Learned!</div>
                      <p className="text-[13px] text-text-dim mb-5">
                        Now type a <strong>similar</strong> task and hit <strong className="text-lime">Race</strong> to see the speedup.
                      </p>
                      <button onClick={reset} className="px-7 py-3 bg-lime text-bg rounded-xl text-[13px] font-medium saas-btn-primary">
                        Race with a similar task
                      </button>
                    </div>
                  )}
                  {learnStatus?.status === 'error' && (
                    <div className="mt-8 saas-card p-6 text-center" style={{ borderColor: 'rgba(239,68,68,0.15)', background: 'rgba(239,68,68,0.03)' }}>
                      <div className="text-red-400 text-sm font-medium mb-2">Learning Failed</div>
                      <p className="text-[12px] text-text-muted mb-4">{learnStatus.error}</p>
                      <button onClick={reset} className="px-6 py-2.5 bg-surface border border-border rounded-xl text-[13px] text-text-dim saas-btn">
                        Try again
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ═══ RACING VIEW ═══ */}
        {view === 'racing' && !baselineId && !raceStarting && (
          <div className="flex-1 flex flex-col items-center justify-center relative z-10 px-6 anim-fade-in">
            <div className="text-center max-w-md">
              <div className="w-12 h-12 rounded-2xl bg-lime/10 flex items-center justify-center mx-auto mb-5">
                <ZapIcon size={22} className="text-lime" />
              </div>
              <h2 className="text-[22px] font-serif italic text-text mb-3">Race a task</h2>
              <p className="text-[14px] text-text-dim leading-relaxed mb-8">
                Enter a task similar to one you've already learned. The system will match it to a template and race Playwright against a vanilla agent.
              </p>
              <div className="w-full max-w-[520px] mx-auto">
                <TaskInput
                  onRun={launch}
                  isRunning={false}
                  racePopover={
                    searchingTask ? (
                      <TemplateSearchCard
                        task={searchingTask}
                        onRace={startRace}
                        onLearnInstead={() => learn(searchingTask)}
                        onDismiss={() => setSearchingTask(null)}
                      />
                    ) : undefined
                  }
                />
              </div>
            </div>
          </div>
        )}
        {view === 'racing' && (baselineId || raceStarting) && (
          <div className="flex-1 flex flex-col min-h-0 relative z-10 anim-fade-in">
            <header className="flex-shrink-0 flex items-center gap-4 px-5 h-12 border-b border-border-subtle bg-surface/30 backdrop-blur-sm">
              <div className="flex items-center gap-2.5 flex-shrink-0">
                <div className="w-[7px] h-[7px] rounded-full bg-lime" />
                <span className="text-[13px] font-medium text-text-dim">Forge</span>
              </div>
              <div className="flex-1">
                <TaskInput onRun={launch} isRunning={isRunning} onStop={reset} compact />
              </div>
              {raceBothComplete ? (
                <span className="text-[11px] font-mono text-text-muted flex-shrink-0">Ready</span>
              ) : (
                <span className="flex items-center gap-1.5 text-[11px] font-mono text-lime flex-shrink-0">
                  <span className="w-[5px] h-[5px] rounded-full bg-lime dot-pulse" /> Live
                </span>
              )}
            </header>
            <div className="flex-1 grid grid-cols-[1fr_1px_1fr] overflow-hidden">
              {/* Baseline column */}
              <div className="flex flex-col p-4 overflow-hidden">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="text-[13px] font-medium text-text-dim">Without Forge</span>
                    <PhaseIndicator phase={basePh} />
                  </div>
                  <Timer elapsedMs={baseTimer.elapsedMs} isComplete={baseStatus?.status === 'complete'} variant="baseline" />
                </div>
                <BrowserEmbed liveUrl={baseStatus?.live_url ?? null} phase={basePh} />
                <div className="mt-3 flex-1 overflow-y-auto saas-inset-sm px-3 py-2">
                  <StepTracker steps={baseStatus?.steps ?? []} phase={basePh} currentStep={baseStatus?.current_step ?? ''} showSummary />
                </div>
              </div>

              {/* Divider with live speedup */}
              <div className="bg-border-subtle relative">
                {liveSpeedup && liveSpeedup > 1.2 && (
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 anim-scale-up">
                    <div className="saas-card-elevated border-lime/15 rounded-full px-4 py-1.5 glow-breathe whitespace-nowrap">
                      <span className="font-mono text-sm font-bold text-lime">{liveSpeedup.toFixed(1)}x</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Rocket column */}
              <div className="flex flex-col p-4 overflow-hidden">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="text-[13px] font-medium text-lime">With Forge</span>
                    <PhaseIndicator phase={rocketPh} />
                  </div>
                  <Timer elapsedMs={rocketTimer.elapsedMs} isComplete={rocketStatus?.status === 'complete'} variant="rocket" />
                </div>
                <BrowserEmbed liveUrl={rocketStatus?.live_url ?? null} phase={rocketPh} />
                <div className="mt-3 flex-1 overflow-y-auto saas-inset-sm px-3 py-2">
                  <StepTracker steps={rocketStatus?.steps ?? []} phase={rocketPh} currentStep={rocketStatus?.current_step ?? ''} showSummary />
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between gap-4 px-5 min-h-9 py-2 border-t border-border-subtle bg-surface/20 text-[11px] font-mono text-text-muted">
              <span className="truncate max-w-sm min-w-0">{currentTask}</span>
              <div className="flex items-center gap-3 flex-shrink-0">
                {totalTimeSavedMs > 0 && (
                  <span className="text-lime/70">
                    {(totalTimeSavedMs / 1000).toFixed(1)}s saved ({raceCount} race{raceCount !== 1 ? 's' : ''})
                  </span>
                )}
                <span>{(baseStatus?.steps.length ?? 0) + (rocketStatus?.steps.length ?? 0)} steps</span>
                {raceBothComplete && (
                  <button
                    type="button"
                    onClick={() => navigate('/results')}
                    className="h-8 px-5 rounded-lg text-[12px] font-medium font-sans bg-lime text-bg hover:brightness-110 transition-all saas-btn-primary"
                  >
                    Done
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ═══ RESULTS VIEW ═══ */}
        {view === 'results' && (!baseStatus || !rocketStatus) && (
          <Navigate to="/learn" replace />
        )}
        {view === 'results' && baseStatus && rocketStatus && (
          <ComparisonCard baselineDurationMs={baseStatus.duration_ms} rocketDurationMs={rocketStatus.duration_ms} onReset={reset} />
        )}

        {/* ═══ BENCHMARKS VIEW ═══ */}
        {view === 'benchmarks' && (
          <BenchmarksPage />
        )}
      </div>
    </div>
  );
}

export default App;
