import { DocPageShell, DocSection } from '../DocPageShell';

export function EnvironmentPage() {
  return (
    <DocPageShell kicker="Reference" title="Configuration">
      <DocSection title="Prerequisites" delay={40}>
        <ul className="space-y-2 text-[14px] text-text-dim leading-relaxed list-none pl-0">
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0">Python</span>
            <span>3.11 or later</span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0">Packages</span>
            <span>
              <code className="font-mono text-[12px] text-sky/90">mcp</code>,{' '}
              <code className="font-mono text-[12px] text-sky/90">httpx</code>,{' '}
              <code className="font-mono text-[12px] text-sky/90">fastapi</code>,{' '}
              <code className="font-mono text-[12px] text-sky/90">browser-use</code>,{' '}
              <code className="font-mono text-[12px] text-sky/90">playwright</code>
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0">Client</span>
            <span>Claude Code, Cursor, Windsurf, or any MCP-compatible assistant</span>
          </li>
        </ul>
      </DocSection>

      <DocSection title="MCP server env" delay={80}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-4">
          The MCP server process needs one variable:
        </p>
        <ul className="text-[13px] text-text-dim space-y-2 font-mono text-[11px] leading-relaxed border border-border rounded-xl p-4 bg-surface/40">
          <li>
            <span className="text-sky/90">FORGED_API_URL</span>{' '}
            <span className="text-text-muted">default: http://localhost:8000</span>
          </li>
        </ul>
      </DocSection>

      <DocSection title="Backend env" delay={120}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-4">
          The FastAPI backend requires these secrets configured on the host:
        </p>
        <ul className="text-[13px] text-text-dim space-y-2 font-mono text-[11px] leading-relaxed border border-border rounded-xl p-4 bg-surface/40">
          <li>
            <span className="text-sky/90">ANTHROPIC_API_KEY</span>{' '}
            <span className="text-text-muted">Claude agent (Sonnet for execution, Haiku for classification)</span>
          </li>
          <li>
            <span className="text-sky/90">BROWSER_USE_API_KEY</span>{' '}
            <span className="text-text-muted">Cloud browser management (BaaS)</span>
          </li>
          <li>
            <span className="text-sky/90">OPENAI_API_KEY</span>{' '}
            <span className="text-text-muted">text-embedding-3-large (3072-dim) for template matching</span>
          </li>
          <li>
            <span className="text-sky/90">SUPABASE_URL</span>{' '}
            <span className="text-text-muted">Supabase project URL</span>
          </li>
          <li>
            <span className="text-sky/90">SUPABASE_SERVICE_ROLE_KEY</span>{' '}
            <span className="text-text-muted">Service role key for template storage</span>
          </li>
          <li>
            <span className="text-sky/90">SUPABASE_DB_URL</span>{' '}
            <span className="text-text-muted">Direct PostgreSQL connection for pgvector queries</span>
          </li>
        </ul>
      </DocSection>

      <DocSection title="Manage the MCP server" delay={160}>
        <pre className="saas-inset-sm rounded-xl p-4 font-mono text-[11px] text-text-dim overflow-x-auto border border-border leading-relaxed">
{`claude mcp list              # see registered servers
claude mcp get forged        # check Forged config
claude mcp remove forged     # uninstall`}
        </pre>
      </DocSection>
    </DocPageShell>
  );
}
