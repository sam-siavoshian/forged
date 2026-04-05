import { EndpointRow } from '../../../components/docs/EndpointBlocks';
import { DocPageShell, DocSection } from '../DocPageShell';

export function EndpointsPage() {
  return (
    <DocPageShell kicker="Reference" title="MCP Tools & HTTP API">
      <DocSection title="MCP Tools" delay={40}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-5">
          These tools are exposed via the MCP server. Any MCP-compatible AI assistant (Claude Code, Cursor, Windsurf) can call them directly.
        </p>
        <div className="space-y-6">
          <div className="border border-border rounded-xl p-4 bg-surface/40">
            <div className="flex items-center gap-2 mb-3">
              <span className="px-2 py-0.5 rounded-md bg-lime/15 text-lime font-mono text-[11px] font-medium">TOOL</span>
              <code className="font-mono text-[13px] text-text font-medium">run_browser_task</code>
            </div>
            <p className="text-[13px] text-text-dim leading-relaxed mb-3">
              Execute a browser automation task. Automatically uses learned templates for speed when available.
              If no template exists, runs a full AI agent and learns from the execution for next time.
            </p>
            <div className="space-y-2 text-[12px] font-mono">
              <div className="flex gap-2">
                <span className="text-text-muted shrink-0">Input:</span>
                <span className="text-sky/90">task</span>
                <span className="text-text-muted">string</span>
                <span className="text-text-muted/60">"Search for headphones on Amazon"</span>
              </div>
              <div className="flex gap-2">
                <span className="text-text-muted shrink-0">Returns:</span>
                <span className="text-text-dim">Result text, mode (rocket/baseline), duration, step breakdown, live browser URL</span>
              </div>
            </div>
          </div>

          <div className="border border-border rounded-xl p-4 bg-surface/40">
            <div className="flex items-center gap-2 mb-3">
              <span className="px-2 py-0.5 rounded-md bg-lime/15 text-lime font-mono text-[11px] font-medium">TOOL</span>
              <code className="font-mono text-[13px] text-text font-medium">list_learned_skills</code>
            </div>
            <p className="text-[13px] text-text-dim leading-relaxed mb-3">
              List browser automation skills that Forged has learned. Shows confidence scores, step counts, and average speedup per template.
            </p>
            <div className="space-y-2 text-[12px] font-mono">
              <div className="flex gap-2">
                <span className="text-text-muted shrink-0">Input:</span>
                <span className="text-sky/90">domain</span>
                <span className="text-text-muted">string | null</span>
                <span className="text-text-muted/60">optional filter, e.g. "amazon.com"</span>
              </div>
              <div className="flex gap-2">
                <span className="text-text-muted shrink-0">Returns:</span>
                <span className="text-text-dim">List of templates with confidence, usage count, and speedup</span>
              </div>
            </div>
          </div>
        </div>
      </DocSection>

      <DocSection title="HTTP API" delay={80}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-5">
          The MCP server calls these endpoints internally. You can also use them directly for custom integrations.
        </p>
        <div className="space-y-6">
          <EndpointRow
            method="POST"
            path="/chat"
            res='{ "session_id": string }'
            note="Auto mode: template match found  → Playwright + agent handoff; no match → full agent + auto-learn."
          />
          <EndpointRow
            method="GET"
            path="/status/{session_id}"
            res="SessionStatus"
            note="Poll for real-time progress. Steps, live_url, phase, result text, template_match metadata."
          />
          <EndpointRow
            method="GET"
            path="/templates"
            res="Template[]"
            note="All learned templates with confidence, step counts, and duration averages."
          />
          <EndpointRow
            method="POST"
            path="/learn"
            res='{ "session_id": string }'
            note="Training mode: agent runs task, template extracted from trace, stored in Supabase."
          />
          <EndpointRow
            method="POST"
            path="/compare"
            res='{ "baseline_session_id", "rocket_session_id" }'
            note="Benchmark: baseline vs Forged in parallel for the same task."
          />
          <EndpointRow
            method="POST"
            path="/search-template"
            res='{ found, template_id, similarity, confidence_band, ... }'
            note="Embedding search only. Does not start a browser."
          />
          <EndpointRow
            method="GET"
            path="/health"
            res='{ "status", "version", "sessions_active" }'
            note="Readiness check and active session count."
          />
        </div>
      </DocSection>
    </DocPageShell>
  );
}
