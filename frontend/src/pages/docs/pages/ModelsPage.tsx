import { DocPageShell, DocSection } from '../DocPageShell';

export function ModelsPage() {
  return (
    <DocPageShell kicker="Reference" title="Response types">
      <DocSection title="run_browser_task response" delay={40}>
        <p className="text-[13px] text-text-dim mb-4 leading-relaxed">
          The MCP tool returns a formatted text string. Here are the fields included:
        </p>

        <div className="border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 bg-surface/40 border-b border-border">
            <span className="font-mono text-[11px] text-lime/90 font-medium">When a template was matched (rocket mode)</span>
          </div>
          <pre className="p-4 font-mono text-[11px] text-text-dim leading-relaxed overflow-x-auto">
{`Result: Successfully logged into staging at https://myapp.com
Mode: rocket (learned template matched, 94% confidence)
Duration: 2.3s
Steps: 5 rocket (Playwright) + 2 agent (Claude)
Live browser: https://browser.use/session/abc123`}
          </pre>
        </div>

        <div className="border border-border rounded-xl overflow-hidden mt-4">
          <div className="px-4 py-2.5 bg-surface/40 border-b border-border">
            <span className="font-mono text-[11px] text-amber-400/90 font-medium">When no template exists (baseline + learn)</span>
          </div>
          <pre className="p-4 font-mono text-[11px] text-text-dim leading-relaxed overflow-x-auto">
{`Result: Successfully searched for 'headphones' on Amazon
Mode: baseline (no template found — learning for next time)
Duration: 18.4s
Steps: 0 rocket + 11 agent (Claude)
Template learned: Search for {{query}} on amazon.com
Next run will be faster.`}
          </pre>
        </div>

        <div className="border border-border rounded-xl overflow-hidden mt-4">
          <div className="px-4 py-2.5 bg-surface/40 border-b border-border">
            <span className="font-mono text-[11px] text-red-400/90 font-medium">On error or timeout</span>
          </div>
          <pre className="p-4 font-mono text-[11px] text-text-dim leading-relaxed overflow-x-auto">
{`TIMEOUT: Task did not complete within 120s.
Session ID: abc-123
Steps completed before timeout: 4
  - Navigate to https://example.com
  - Click search button
  - Fill search input`}
          </pre>
        </div>
      </DocSection>

      <DocSection title="list_learned_skills response" delay={80}>
        <div className="border border-border rounded-xl overflow-hidden">
          <pre className="p-4 font-mono text-[11px] text-text-dim leading-relaxed overflow-x-auto">
{`Learned Skills (3 total):

1. amazon.com — "Search for {{query}} on Amazon"
   Confidence: 89% | Steps: 4 rocket + 3 agent | Avg speedup: 4.2x
   Used 7 times (6 success, 1 failure)

2. github.com — "Go to GitHub trending and extract top repos"
   Confidence: 95% | Steps: 3 rocket + 2 agent | Avg speedup: 6.1x
   Used 12 times (12 success)

3. myapp.com — "Log into staging at {{url}}"
   Confidence: 72% | Steps: 5 rocket + 0 agent | Avg speedup: 8.3x
   Used 3 times (2 success, 1 failure)`}
          </pre>
        </div>
      </DocSection>

      <DocSection title="SessionStatus (HTTP API)" delay={120}>
        <p className="text-[13px] text-text-dim mb-4 leading-relaxed">
          Returned by <code className="font-mono text-[12px]">GET /status/&#123;id&#125;</code>. The MCP server polls this internally.
        </p>
        <ul className="text-[13px] text-text-dim space-y-2 font-mono text-[11px] leading-relaxed border border-border rounded-xl p-4 bg-surface/40">
          <li><span className="text-lime/90">session_id</span> string</li>
          <li><span className="text-lime/90">status</span> pending | running | complete | error</li>
          <li><span className="text-lime/90">phase</span> idle | rocket | agent | complete | learning</li>
          <li><span className="text-lime/90">mode_used</span> rocket | baseline_learn | null</li>
          <li><span className="text-lime/90">duration_ms</span> number</li>
          <li><span className="text-lime/90">steps</span> StepInfo[] — each with type, description, durationMs</li>
          <li><span className="text-lime/90">result</span> string | null — agent's final answer</li>
          <li><span className="text-lime/90">live_url</span> string | null — embedded browser session</li>
          <li><span className="text-lime/90">template_match</span> &#123; similarity, domain, task_pattern &#125; | null</li>
          <li><span className="text-lime/90">error</span> string | null</li>
        </ul>
      </DocSection>
    </DocPageShell>
  );
}
