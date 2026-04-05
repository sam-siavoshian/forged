/** Search targets for Cmd+K — update when API sections change. */
export interface DocSearchItem {
  id: string;
  title: string;
  path: string;
  keywords: string[];
}

export const DOC_SEARCH_INDEX: DocSearchItem[] = [
  {
    id: 'overview',
    title: 'Overview',
    path: '/docs/overview',
    keywords: ['forged', 'mcp', 'browser', 'playwright', 'template', 'self-improve', 'learn', 'agent', 'sdk', 'claude code'],
  },
  {
    id: 'integration',
    title: 'Quick Start',
    path: '/docs/integration',
    keywords: ['install', 'setup', 'curl', 'mcp', 'claude code', 'cursor', 'windsurf', 'quick start', 'getting started'],
  },
  {
    id: 'endpoints',
    title: 'MCP Tools & API',
    path: '/docs/endpoints',
    keywords: ['run_browser_task', 'list_learned_skills', 'mcp', 'tool', 'api', 'post', 'get', 'chat', 'templates', 'health'],
  },
  {
    id: 'models',
    title: 'Response Types',
    path: '/docs/models',
    keywords: ['response', 'run_browser_task', 'list_learned_skills', 'result', 'mode', 'rocket', 'baseline', 'speedup', 'confidence'],
  },
  {
    id: 'environment',
    title: 'How It Works',
    path: '/docs/environment',
    keywords: [
      'confidence',
      'threshold',
      'similarity',
      'pgvector',
      'fixed',
      'parameterized',
      'dynamic',
      'step classification',
      'template matching',
      'clients',
      'cursor',
      'windsurf',
    ],
  },
  {
    id: 'tool-run',
    title: 'run_browser_task',
    path: '/docs/endpoints',
    keywords: ['run', 'browser', 'task', 'execute', 'automation', 'learn', 'template'],
  },
  {
    id: 'tool-list',
    title: 'list_learned_skills',
    path: '/docs/endpoints',
    keywords: ['list', 'skills', 'templates', 'learned', 'domain', 'confidence'],
  },
];
