import type { RunStatus, Template } from './types';

const MOCK_MODE = import.meta.env.VITE_MOCK_MODE === 'true';
const API_BASE = '/api';

// ─── Mock Data ───────────────────────────────────────────────

const MOCK_BASELINE_STEPS = [
  { desc: 'Navigate to google.com', delayMs: 3000 },
  { desc: 'Find search input field', delayMs: 2500 },
  { desc: 'Type search query', delayMs: 4000 },
  { desc: 'Click search button', delayMs: 2000 },
  { desc: 'Wait for results to load', delayMs: 3500 },
  { desc: 'Scan search results', delayMs: 5000 },
  { desc: 'Click first relevant result', delayMs: 3000 },
  { desc: 'Wait for page to load', delayMs: 4000 },
  { desc: 'Extract page content', delayMs: 6000 },
  { desc: 'Verify content matches query', delayMs: 4000 },
];

const MOCK_ROCKET_STEPS_PLAYWRIGHT = [
  { desc: 'Navigate to google.com', delayMs: 200 },
  { desc: 'Type search query', delayMs: 150 },
  { desc: 'Click search button', delayMs: 100 },
  { desc: 'Wait for results', delayMs: 300 },
  { desc: 'Click first result', delayMs: 150 },
  { desc: 'Wait for page load', delayMs: 250 },
];

const MOCK_ROCKET_STEPS_AGENT = [
  { desc: 'Analyze page structure', delayMs: 1500 },
  { desc: 'Extract relevant content', delayMs: 2000 },
  { desc: 'Verify content accuracy', delayMs: 1500 },
];

const MOCK_TEMPLATES: Template[] = [
  {
    id: 'tmpl_1',
    domain: 'google.com',
    pattern: 'Search for {query} on Google',
    confidence: 0.95,
    steps: [
      { id: 's1', description: 'Navigate to google.com', type: 'fixed' },
      { id: 's2', description: 'Type {query} in search box', type: 'parameterized' },
      { id: 's3', description: 'Click search button', type: 'fixed' },
      { id: 's4', description: 'Wait for results', type: 'fixed' },
      { id: 's5', description: 'Click first relevant result', type: 'fixed' },
      { id: 's6', description: 'Wait for page load', type: 'fixed', handoff: true },
      { id: 's7', description: 'Analyze page content', type: 'dynamic' },
      { id: 's8', description: 'Extract information', type: 'dynamic' },
    ],
    created_at: '2024-01-15T10:30:00Z',
    uses: 24,
  },
  {
    id: 'tmpl_2',
    domain: 'amazon.com',
    pattern: 'Find {product} on Amazon',
    confidence: 0.88,
    steps: [
      { id: 's1', description: 'Navigate to amazon.com', type: 'fixed' },
      { id: 's2', description: 'Search for {product}', type: 'parameterized' },
      { id: 's3', description: 'Apply filters', type: 'dynamic' },
      { id: 's4', description: 'Select best match', type: 'dynamic' },
    ],
    created_at: '2024-01-14T08:20:00Z',
    uses: 12,
  },
  {
    id: 'tmpl_3',
    domain: 'github.com',
    pattern: 'Star repository {repo}',
    confidence: 0.92,
    steps: [
      { id: 's1', description: 'Navigate to github.com/{repo}', type: 'parameterized' },
      { id: 's2', description: 'Click star button', type: 'fixed' },
      { id: 's3', description: 'Verify star added', type: 'fixed' },
    ],
    created_at: '2024-01-13T14:00:00Z',
    uses: 7,
  },
];

// ─── Mock Session State ──────────────────────────────────────

interface MockSession {
  id: string;
  mode: 'baseline' | 'rocket';
  startedAt: number;
  steps: { desc: string; delayMs: number; type: 'playwright' | 'agent' }[];
  currentStepIndex: number;
  accumulatedMs: number;
}

const mockSessions = new Map<string, MockSession>();

function createMockSession(mode: 'baseline' | 'rocket'): string {
  const id = `mock_${mode}_${Date.now()}`;
  const steps =
    mode === 'baseline'
      ? MOCK_BASELINE_STEPS.map((s) => ({ ...s, type: 'agent' as const }))
      : [
          ...MOCK_ROCKET_STEPS_PLAYWRIGHT.map((s) => ({ ...s, type: 'playwright' as const })),
          ...MOCK_ROCKET_STEPS_AGENT.map((s) => ({ ...s, type: 'agent' as const })),
        ];

  mockSessions.set(id, {
    id,
    mode,
    startedAt: Date.now(),
    steps,
    currentStepIndex: -1,
    accumulatedMs: 0,
  });

  return id;
}

function getMockStatus(sessionId: string): RunStatus {
  const session = mockSessions.get(sessionId);
  if (!session) {
    return {
      session_id: sessionId,
      status: 'error',
      phase: 'error',
      current_step: '',
      steps: [],
      live_url: null,
      duration_ms: 0,
      error: 'Session not found',
    };
  }

  const elapsed = Date.now() - session.startedAt;

  // Advance steps based on elapsed time
  let totalDelay = 0;
  let newIndex = -1;
  for (let i = 0; i < session.steps.length; i++) {
    totalDelay += session.steps[i].delayMs;
    if (elapsed >= totalDelay - session.steps[i].delayMs) {
      newIndex = i;
    }
  }
  session.currentStepIndex = Math.min(newIndex, session.steps.length - 1);

  const isComplete = elapsed >= totalDelay;
  const completedSteps = session.steps
    .slice(0, session.currentStepIndex + 1)
    .map((s, i) => ({
      id: `step_${i}`,
      description: s.desc,
      type: s.type,
      timestamp: session.startedAt + session.steps.slice(0, i).reduce((acc, st) => acc + st.delayMs, 0),
      durationMs: s.delayMs,
    }));

  const currentStep = session.steps[session.currentStepIndex];
  const playwrightCount =
    session.mode === 'rocket' ? MOCK_ROCKET_STEPS_PLAYWRIGHT.length : 0;

  let phase: RunStatus['phase'];
  if (isComplete) {
    phase = 'complete';
  } else if (session.mode === 'rocket' && session.currentStepIndex < playwrightCount) {
    phase = 'rocket';
  } else {
    phase = 'agent';
  }

  return {
    session_id: sessionId,
    status: isComplete ? 'complete' : 'running',
    phase,
    current_step: currentStep?.desc ?? 'Initializing...',
    steps: completedSteps,
    live_url: null,
    duration_ms: isComplete ? totalDelay : elapsed,
  };
}

// ─── API Functions ───────────────────────────────────────────

export async function startRun(task: string, mode: 'baseline' | 'rocket'): Promise<string> {
  if (MOCK_MODE) {
    return createMockSession(mode);
  }

  const endpoint = mode === 'baseline' ? `${API_BASE}/run-baseline` : `${API_BASE}/run-rocket`;
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to start ${mode} run: ${err}`);
  }

  const data = await res.json();
  return data.session_id;
}

export async function startCompare(task: string): Promise<{ baseline_session_id: string; rocket_session_id: string }> {
  if (MOCK_MODE) {
    return {
      baseline_session_id: createMockSession('baseline'),
      rocket_session_id: createMockSession('rocket'),
    };
  }

  const res = await fetch(`${API_BASE}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task }),
  });

  if (!res.ok) throw new Error(`Failed to start comparison: ${await res.text()}`);
  return res.json();
}

export async function startLearn(task: string): Promise<string> {
  if (MOCK_MODE) {
    return `mock_learn_${Date.now()}`;
  }

  const res = await fetch(`${API_BASE}/learn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task }),
  });

  if (!res.ok) throw new Error(`Failed to start learning: ${await res.text()}`);
  const data = await res.json();
  return data.session_id;
}

export async function getStatus(sessionId: string): Promise<RunStatus> {
  if (MOCK_MODE) {
    return getMockStatus(sessionId);
  }

  const res = await fetch(`${API_BASE}/status/${encodeURIComponent(sessionId)}`);
  if (!res.ok) throw new Error(`Failed to get status: ${await res.text()}`);
  return res.json();
}

export async function getTemplates(): Promise<Template[]> {
  if (MOCK_MODE) {
    return MOCK_TEMPLATES;
  }

  const res = await fetch(`${API_BASE}/templates`);
  if (!res.ok) throw new Error(`Failed to get templates: ${await res.text()}`);
  return res.json();
}
