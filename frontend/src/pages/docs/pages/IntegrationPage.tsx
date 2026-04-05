import { DocPageShell, DocSection } from '../DocPageShell';

const SETUP_CMD = `curl -fsSL https://raw.githubusercontent.com/sam-siavoshian/browser-use-rl-env/main/setup_mcp.sh | bash`;

export function IntegrationPage() {
  return (
    <DocPageShell kicker="Quick Start" title="Install in one command">
      <DocSection title="Install" delay={40}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-4">
          The setup wizard finds your Python, installs dependencies, and registers
          Forged with Claude Code. Takes about 60 seconds.
        </p>
        <div className="border border-lime/20 rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 bg-lime/[0.04] border-b border-lime/10 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-lime/60" />
            <span className="text-[11px] text-lime/80 font-medium font-mono">Terminal</span>
          </div>
          <pre className="p-4 font-mono text-[12px] text-text leading-relaxed overflow-x-auto whitespace-pre-wrap break-all bg-black/20">
            {SETUP_CMD}
          </pre>
        </div>
        <div className="flex gap-4 mt-4">
          <div className="flex items-center gap-2 text-[12px] text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full bg-text-muted/40" />
            Python 3.11+
          </div>
          <div className="flex items-center gap-2 text-[12px] text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full bg-text-muted/40" />
            Claude Code CLI
          </div>
        </div>
      </DocSection>

      <DocSection title="Try it" delay={80}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-4">
          Open Claude Code and try these. Each task gets faster on repeat:
        </p>
        <div className="space-y-3">
          {[
            { task: 'Go to news.ycombinator.com and get the top story', note: 'News extraction' },
            { task: 'Search for mechanical keyboards on Amazon', note: 'E-commerce search' },
            { task: 'Go to github.com/trending and get the #1 repo', note: 'Data scraping' },
          ].map(({ task, note }) => (
            <div key={task} className="flex gap-3 items-start">
              <span className="text-[11px] text-text-muted font-mono shrink-0 pt-1 w-24">{note}</span>
              <div className="flex-1 border border-border rounded-lg px-3 py-2 bg-surface/30">
                <p className="text-[13px] text-text italic leading-relaxed">"{task}"</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5 p-4 rounded-xl bg-lime/[0.04] border border-lime/10">
          <p className="text-[13px] text-text-dim leading-relaxed">
            <strong className="text-lime font-medium">Pro tip:</strong> Run the same task twice. The second run
            skips learned steps entirely — no LLM calls for navigation, login, or search. Just Playwright at
            millisecond speed.
          </p>
        </div>
      </DocSection>
    </DocPageShell>
  );
}
