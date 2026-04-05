import { DocPageShell, DocSection } from '../DocPageShell';

export function OverviewPage() {
  return (
    <DocPageShell kicker="Forged" title="Self-improving browser automation">
      <DocSection title="What Forged does" delay={40}>
        <p className="text-[15px] text-text-dim leading-relaxed max-w-[52ch]">
          Forged is an <strong className="text-text font-medium">MCP server</strong> that gives AI assistants a learning layer for browser automation.
          The first time your AI runs a task, it uses a full LLM agent. Forged records the trace, extracts a reusable template, and replays
          deterministic steps via <strong className="text-text font-medium">Playwright</strong> on subsequent runs. The agent only handles steps
          that actually require reasoning.
        </p>
        <p className="text-[14px] text-text-muted leading-relaxed mt-3 max-w-[52ch]">
          Works with Claude Code, Cursor, Windsurf, and any MCP-compatible assistant.
        </p>
      </DocSection>

      <DocSection title="How it gets faster" delay={80}>
        <ul className="space-y-4 text-[14px] text-text-dim leading-relaxed list-none pl-0">
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0 w-8">Run 1</span>
            <span>
              Full AI agent browses the site. Every step goes through Claude.{' '}
              <strong className="text-text font-medium">~45 seconds.</strong> Forged records the trace and extracts a template.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-amber-400/80 text-[12px] shrink-0 w-8">Run 2</span>
            <span>
              Login and navigation replay via Playwright at millisecond speed. Agent handles only the dynamic parts.{' '}
              <strong className="text-text font-medium">~12 seconds.</strong> Template confidence increases.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-sky/80 text-[12px] shrink-0 w-8">Run 5</span>
            <span>
              80% of steps are deterministic Playwright, 20% agent reasoning.{' '}
              <strong className="text-text font-medium">~3 seconds.</strong> No LLM calls for learned steps.
            </span>
          </li>
        </ul>
      </DocSection>

      <DocSection title="Under the hood" delay={120}>
        <ul className="space-y-3 text-[14px] text-text-dim leading-relaxed list-none pl-0">
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0">Match</span>
            <span>
              Three-layer pipeline: domain extraction, action classification, then pgvector embedding similarity search (3072-dim) to find matching templates.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0">Rocket</span>
            <span>
              Deterministic Playwright execution of template steps (navigate, click, fill) at millisecond speed. Falls back to agent on selector failure.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0">Learn</span>
            <span>
              LLM analyzes traces, classifies steps as FIXED, PARAMETERIZED, or DYNAMIC, and stores reusable templates with confidence scores that update after every execution.
            </span>
          </li>
        </ul>
      </DocSection>
    </DocPageShell>
  );
}
