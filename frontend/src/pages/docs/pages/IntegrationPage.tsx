import { DocPageShell, DocSection } from '../DocPageShell';

const SETUP_CMD = `curl -fsSL https://raw.githubusercontent.com/sam-siavoshian/browser-use-rl-env/main/setup_mcp.sh | bash`;

export function IntegrationPage() {
  return (
    <DocPageShell kicker="Quick Start" title="Set up Forged in 60 seconds">
      <DocSection title="One-command install" delay={40}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-3">
          Run this in your terminal. The wizard detects your Python, finds the repo, installs dependencies, and registers Forged with Claude Code automatically.
        </p>
        <pre className="saas-inset-sm rounded-xl p-4 font-mono text-[11px] text-text-dim overflow-x-auto border border-border leading-relaxed whitespace-pre-wrap break-all">
          {SETUP_CMD}
        </pre>
        <p className="mt-3 text-[12px] text-text-muted leading-relaxed">
          Requires <strong className="text-text-dim">Python 3.11+</strong> and the{' '}
          <strong className="text-text-dim">Claude Code CLI</strong>. The script uses{' '}
          <code className="font-mono text-[11px] text-sky/90">claude mcp add</code> under the hood.
        </p>
      </DocSection>

      <DocSection title="Manual setup" delay={80}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-3">
          If you prefer to configure manually, add this to your Claude Code MCP settings:
        </p>
        <pre className="saas-inset-sm rounded-xl p-4 font-mono text-[11px] text-text-dim overflow-x-auto border border-border leading-relaxed">
{`claude mcp add -s user \\
  -e FORGED_API_URL=http://localhost:8000 \\
  forged -- python /path/to/mcp_server.py`}
        </pre>
      </DocSection>

      <DocSection title="Start the backend" delay={120}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-3">
          Forged's MCP server talks to the FastAPI backend. Start it before using any tools:
        </p>
        <pre className="saas-inset-sm rounded-xl p-4 font-mono text-[11px] text-text-dim overflow-x-auto border border-border leading-relaxed">
{`cd /path/to/forged && ./dev.sh`}
        </pre>
        <p className="mt-3 text-[12px] text-text-muted leading-relaxed">
          This starts both the Python backend (port 8000) and the React frontend (port 5173).
        </p>
      </DocSection>

      <DocSection title="Try it" delay={160}>
        <p className="text-[14px] text-text-dim leading-relaxed mb-3">
          Open Claude Code and ask it to run a browser task. Forged handles everything:
        </p>
        <ul className="space-y-2 text-[14px] text-text-dim leading-relaxed list-none pl-0">
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0 pt-0.5">1.</span>
            <span>
              <em className="text-text">"Go to news.ycombinator.com and get the top story"</em> — first run, full agent, learns a template.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0 pt-0.5">2.</span>
            <span>
              Run the same task again — Forged replays learned steps via Playwright. Visibly faster.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-mono text-lime/80 text-[12px] shrink-0 pt-0.5">3.</span>
            <span>
              Ask <em className="text-text">"What skills has Forged learned?"</em> — Claude calls <code className="font-mono text-[12px] text-sky/90">list_learned_skills</code>.
            </span>
          </li>
        </ul>
      </DocSection>
    </DocPageShell>
  );
}
