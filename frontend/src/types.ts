export type RunMode = 'baseline' | 'rocket' | 'compare' | 'learn';

export type Phase = 'idle' | 'rocket' | 'agent' | 'complete' | 'error' | 'learning';

export type StepType = 'playwright' | 'agent';

export type ActionType = 'navigate' | 'click' | 'fill' | 'press' | 'extract' | 'search_web' | 'scroll' | 'done' | 'template_match' | 'agent_action';

export interface Step {
  id: string;
  description: string;
  type: StepType;
  timestamp: number;
  durationMs?: number;
  action_type?: ActionType;
  details?: Record<string, any>;
}

export interface RunStatus {
  session_id: string;
  status: 'pending' | 'running' | 'complete' | 'error' | 'not_found';
  phase: Phase;
  current_step: string;
  steps: Step[];
  live_url: string | null;
  duration_ms: number;
  error?: string;
  result?: string;
  agent_complete?: boolean;
  agent_duration_ms?: number;
  mode_used?: 'rocket' | 'baseline_learn';
  template_match?: { similarity: number; domain: string; task_pattern: string };
  task?: string;
}

export interface ChatSessionSummary {
  session_id: string;
  task: string;
  status: string;
  mode_used: 'rocket' | 'baseline_learn' | null;
  duration_ms: number;
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
