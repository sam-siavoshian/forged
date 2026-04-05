import { EndpointRow } from '../../../components/docs/EndpointBlocks';
import { DocPageShell, DocSection } from '../DocPageShell';

export function EndpointsPage() {
  return (
    <DocPageShell kicker="Reference" title="MCP Tools & HTTP API">
      <DocSection title="MCP Tools (what your AI calls)" delay={40}>
        <p className="text-[13px] text-text-muted leading-relaxed mb-5">
          Two tools. That's it. Your AI assistant discovers them automatically via MCP.
        </p>
        <div className="space-y-5">
          <div className="border border-border rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 bg-surface/40 border-b border-border">
              <span className="px-2 py-0.5 rounded-md bg-lime/15 text-lime font-mono text-[10px] font-semibold">TOOL</span>
              <code className="font-mono text-[13px] text-text font-semibold tracking-tight">run_browser_task</code>
            </div>
            <div className="px-4 py-3 space-y-3">
              <p className="text-[13px] text-text-dim leading-relaxed">
                Execute any browser task. Forged checks for a learned template, replays deterministic
                steps via Playwright, hands dynamic steps to the AI agent, and auto-learns for next time.
              </p>
              <div className="rounded-lg bg-black/20 p-3 space-y-1.5 font-mono text-[11px]">
                <div className="flex gap-2 items-baseline">
                  <span className="text-text-muted w-14 shrink-0">input</span>
                  <span className="text-sky/90">task</span>
                  <span className="text-text-muted/60">string</span>
                </div>
                <div className="flex gap-2 items-baseline">
                  <span className="text-text-muted w-14 shrink-0">returns</span>
                  <span className="text-text-dim">result, mode, duration, steps, live_url</span>
                </div>
              </div>
              <div className="rounded-lg bg-black/20 p-3">
                <p className="font-mono text-[11px] text-text-muted mb-1.5">Example</p>
                <p className="font-mono text-[12px] text-text italic">
                  "Search for wireless headphones under $50 on Amazon"
                </p>
              </div>
            </div>
          </div>

          <div className="border border-border rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 bg-surface/40 border-b border-border">
              <span className="px-2 py-0.5 rounded-md bg-lime/15 text-lime font-mono text-[10px] font-semibold">TOOL</span>
              <code className="font-mono text-[13px] text-text font-semibold tracking-tight">list_learned_skills</code>
            </div>
            <div className="px-4 py-3 space-y-3">
              <p className="text-[13px] text-text-dim leading-relaxed">
                See what Forged has learned. Shows each template with its domain, pattern, confidence
                score, usage stats, and average speedup.
              </p>
              <div className="rounded-lg bg-black/20 p-3 space-y-1.5 font-mono text-[11px]">
                <div className="flex gap-2 items-baseline">
                  <span className="text-text-muted w-14 shrink-0">input</span>
                  <span className="text-sky/90">domain</span>
                  <span className="text-text-muted/60">string | null — optional filter</span>
                </div>
                <div className="flex gap-2 items-baseline">
                  <span className="text-text-muted w-14 shrink-0">returns</span>
                  <span className="text-text-dim">list of templates with confidence and speedup</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </DocSection>

      <DocSection title="HTTP API (under the hood)" delay={100}>
        <p className="text-[13px] text-text-muted leading-relaxed mb-5">
          The MCP server calls these internally. Use them directly for custom integrations.
        </p>
        <div className="space-y-4">
          <EndpointRow
            method="POST"
            path="/chat"
            res='{ "session_id": string }'
            note="Auto mode. Template match → Playwright + handoff. No match → full agent + auto-learn."
          />
          <EndpointRow
            method="GET"
            path="/status/{session_id}"
            res="SessionStatus"
            note="Real-time progress. Steps, live browser URL, phase, result text, template match info."
          />
          <EndpointRow
            method="GET"
            path="/templates"
            res="Template[]"
            note="All learned templates. Confidence scores, step counts, duration averages."
          />
          <EndpointRow
            method="POST"
            path="/learn"
            res='{ "session_id": string }'
            note="Training mode. Run the agent, extract a template, store it."
          />
          <EndpointRow
            method="POST"
            path="/compare"
            res='{ "baseline_session_id", "rocket_session_id" }'
            note="Race baseline vs Forged on the same task. Side-by-side benchmark."
          />
          <EndpointRow
            method="GET"
            path="/health"
            res='{ "status", "version", "sessions_active" }'
            note="Readiness check."
          />
        </div>
      </DocSection>
    </DocPageShell>
  );
}
