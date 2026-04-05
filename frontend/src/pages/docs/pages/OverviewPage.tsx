import { DocPageShell, DocSection } from '../DocPageShell';

export function OverviewPage() {
  return (
    <DocPageShell kicker="Forged" title="Browser automation that learns">
      <DocSection title="The problem" delay={40}>
        <p className="text-[15px] text-text-dim leading-relaxed max-w-[52ch]">
          Every time an AI agent browses a website, it starts from zero. Login flows, navigation, search bars —
          the agent re-discovers all of it through expensive LLM calls.{' '}
          <strong className="text-text font-medium">3-5 seconds per step. Every single time.</strong>
        </p>
      </DocSection>

      <DocSection title="The fix" delay={80}>
        <p className="text-[15px] text-text-dim leading-relaxed max-w-[52ch]">
          Forged is an <strong className="text-text font-medium">MCP server</strong> that sits between your AI assistant
          and the browser. It records what works, extracts reusable templates, and replays deterministic steps via
          Playwright at millisecond speed. The LLM only handles steps that genuinely need reasoning.
        </p>
        <p className="text-[14px] text-text-muted leading-relaxed mt-3 max-w-[52ch]">
          One tool. Drop it into Claude Code, Cursor, or Windsurf. It gets faster every time you use it.
        </p>
      </DocSection>

      <DocSection title="Real benchmark" delay={120}>
        <div className="border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 bg-surface/40 border-b border-border">
            <span className="text-[12px] text-text-muted font-medium">
              Task: "Go to news.ycombinator.com and get the top story"
            </span>
          </div>
          <div className="divide-y divide-border">
            <div className="flex items-center gap-4 px-4 py-3">
              <span className="font-mono text-[11px] text-text-muted w-10 shrink-0">Run 1</span>
              <div className="flex-1">
                <div className="h-2 rounded-full bg-amber-400/20 overflow-hidden">
                  <div className="h-full rounded-full bg-amber-400/70" style={{ width: '100%' }} />
                </div>
              </div>
              <span className="font-mono text-[13px] text-amber-400 w-16 text-right font-medium">47.4s</span>
              <span className="text-[11px] text-text-muted w-28 text-right">full agent</span>
            </div>
            <div className="flex items-center gap-4 px-4 py-3">
              <span className="font-mono text-[11px] text-text-muted w-10 shrink-0">Run 2</span>
              <div className="flex-1">
                <div className="h-2 rounded-full bg-lime/20 overflow-hidden">
                  <div className="h-full rounded-full bg-lime/70" style={{ width: '18.6%' }} />
                </div>
              </div>
              <span className="font-mono text-[13px] text-lime w-16 text-right font-medium">8.8s</span>
              <span className="text-[11px] text-text-muted w-28 text-right">9 Playwright + 1 agent</span>
            </div>
          </div>
          <div className="px-4 py-2.5 bg-lime/[0.04] border-t border-lime/10">
            <span className="font-mono text-[12px] text-lime font-semibold">5.4x faster</span>
            <span className="text-[12px] text-text-muted ml-2">on the second run. Zero config.</span>
          </div>
        </div>
      </DocSection>

      <DocSection title="How it works" delay={160}>
        <div className="space-y-4">
          <div className="flex gap-4 items-start">
            <div className="w-7 h-7 rounded-lg bg-lime/10 border border-lime/20 flex items-center justify-center shrink-0 mt-0.5">
              <span className="font-mono text-[11px] text-lime font-semibold">1</span>
            </div>
            <div>
              <p className="text-[14px] text-text font-medium mb-1">Run a task</p>
              <p className="text-[13px] text-text-dim leading-relaxed">
                Your AI calls <code className="font-mono text-[11px] text-sky/90">run_browser_task</code>.
                Forged checks its template database via pgvector similarity search (3072-dim embeddings).
              </p>
            </div>
          </div>
          <div className="flex gap-4 items-start">
            <div className="w-7 h-7 rounded-lg bg-lime/10 border border-lime/20 flex items-center justify-center shrink-0 mt-0.5">
              <span className="font-mono text-[11px] text-lime font-semibold">2</span>
            </div>
            <div>
              <p className="text-[14px] text-text font-medium mb-1">Match or learn</p>
              <p className="text-[13px] text-text-dim leading-relaxed">
                If a template matches, deterministic steps (navigate, click, fill) replay via Playwright
                in milliseconds. If no match, the full agent runs and Forged learns a template from the trace.
              </p>
            </div>
          </div>
          <div className="flex gap-4 items-start">
            <div className="w-7 h-7 rounded-lg bg-lime/10 border border-lime/20 flex items-center justify-center shrink-0 mt-0.5">
              <span className="font-mono text-[11px] text-lime font-semibold">3</span>
            </div>
            <div>
              <p className="text-[14px] text-text font-medium mb-1">Get smarter</p>
              <p className="text-[13px] text-text-dim leading-relaxed">
                Template confidence updates after every execution. Steps are classified as FIXED
                (deterministic), PARAMETERIZED (same action, different value), or DYNAMIC (needs agent reasoning).
              </p>
            </div>
          </div>
        </div>
      </DocSection>
    </DocPageShell>
  );
}
