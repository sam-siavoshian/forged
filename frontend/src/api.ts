import type { RunStatus, Template, ChatSessionSummary } from './types';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

// ─── API Functions (real backend only, no mocks) ────────────

export async function startRun(task: string, mode: 'baseline' | 'rocket'): Promise<string> {
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
  const res = await fetch(`${API_BASE}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task }),
  });

  if (!res.ok) throw new Error(`Failed to start comparison: ${await res.text()}`);
  return res.json();
}

export async function startLearn(task: string): Promise<string> {
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
  const res = await fetch(`${API_BASE}/status/${encodeURIComponent(sessionId)}`);
  if (!res.ok) throw new Error(`Failed to get status: ${await res.text()}`);
  return res.json();
}

export interface TemplateSearchResult {
  found: boolean;
  template_id?: string;
  task_pattern?: string;
  similarity?: number;
  confidence?: number;
  domain?: string;
  action_type?: string;
  playwright_steps?: number;
  total_steps?: number;
  error?: string;
}

export async function searchTemplate(task: string): Promise<TemplateSearchResult> {
  const res = await fetch(`${API_BASE}/search-template`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task }),
  });
  if (!res.ok) return { found: false, error: await res.text() };
  return res.json();
}

export async function getTemplates(): Promise<Template[]> {
  const res = await fetch(`${API_BASE}/templates`);
  if (!res.ok) throw new Error(`Failed to get templates: ${await res.text()}`);
  return res.json();
}

export async function startChat(task: string): Promise<string> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task }),
  });
  if (!res.ok) throw new Error(`Failed to start chat: ${await res.text()}`);
  const data = await res.json();
  return data.session_id;
}

export async function getChatSessions(): Promise<ChatSessionSummary[]> {
  const res = await fetch(`${API_BASE}/chat/sessions`);
  if (!res.ok) return [];
  return res.json();
}

export interface RaceHistoryEntry {
  task: string;
  baseline_duration_ms: number;
  rocket_duration_ms: number;
  speedup: number;
  rocket_steps: number | null;
  created_at: string;
}

export async function getRaceHistory(): Promise<RaceHistoryEntry[]> {
  const res = await fetch(`${API_BASE}/race-history`);
  if (!res.ok) return [];
  return res.json();
}
