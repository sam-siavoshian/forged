export type RunMode = 'baseline' | 'rocket' | 'compare' | 'learn';

export type Phase = 'idle' | 'rocket' | 'agent' | 'complete' | 'error' | 'learning';

export type StepType = 'playwright' | 'agent';

export interface Step {
  id: string;
  description: string;
  type: StepType;
  timestamp: number;
  durationMs?: number;
}

export interface RunStatus {
  session_id: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  phase: Phase;
  current_step: string;
  steps: Step[];
  live_url: string | null;
  duration_ms: number;
  error?: string;
}

export interface Template {
  id: string;
  domain: string;
  pattern: string;
  confidence: number;
  steps: TemplateStep[];
  created_at: string;
  uses: number;
}

export interface TemplateStep {
  id: string;
  description: string;
  type: 'fixed' | 'parameterized' | 'dynamic';
  handoff?: boolean;
}

export interface ComparisonResult {
  baseline_duration_ms: number;
  rocket_duration_ms: number;
  speedup: number;
  baseline_steps: number;
  rocket_steps: number;
}

export interface RunSession {
  sessionId: string;
  mode: 'baseline' | 'rocket';
  status: RunStatus | null;
  startTime: number;
  elapsedMs: number;
  isPolling: boolean;
}
