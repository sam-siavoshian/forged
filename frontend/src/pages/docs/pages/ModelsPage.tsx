import { DocPageShell, DocSection } from '../DocPageShell';

export function ModelsPage() {
  return (
    <DocPageShell kicker="Reference" title="What you get back">
      <DocSection title="run_browser_task" delay={40}>
        <p className="text-[13px] text-text-muted leading-relaxed mb-4">
          Returns a text summary with these fields. The format adapts based on what happened.
        </p>

        <div className="space-y-4">
          <div className="border border-lime/20 rounded-xl overflow-hidden">
            <div className="px-4 py-2.5 bg-lime/[0.04] border-b border-lime/10 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-lime/60" />
              <span className="font-mono text-[11px] text-lime/80 font-medium">Template matched — fast path</span>
            </div>
            <pre className="p-4 font-mono text-[11px] text-text-dim leading-[1.7] overflow-x-auto">
{`Result: The top story title is: "The machines are fine..."
Mode: rocket (learned template matched, 79% confidence)
Duration: 8.8s
Steps: 9 rocket (Playwright) + 1 agent (Claude)
Live browser: https://live.browser-use.com?wss=...`}
            </pre>
          </div>

          <div className="border border-amber-400/20 rounded-xl overflow-hidden">
            <div className="px-4 py-2.5 bg-amber-400/[0.04] border-b border-amber-400/10 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400/60" />
              <span className="font-mono text-[11px] text-amber-400/80 font-medium">No template — learning</span>
            </div>
            <pre className="p-4 font-mono text-[11px] text-text-dim leading-[1.7] overflow-x-auto">
{`Result: Successfully searched for 'headphones' on Amazon
Mode: baseline (no template found — learning for next time)
Duration: 18.4s
Steps: 0 rocket + 11 agent (Claude)
Template learned: Search for {{query}} on amazon.com
Next run will be faster.`}
            </pre>
          </div>

          <div className="border border-red-400/20 rounded-xl overflow-hidden">
            <div className="px-4 py-2.5 bg-red-400/[0.04] border-b border-red-400/10 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-400/60" />
              <span className="font-mono text-[11px] text-red-400/80 font-medium">Timeout or error</span>
            </div>
            <pre className="p-4 font-mono text-[11px] text-text-dim leading-[1.7] overflow-x-auto">
{`TIMEOUT: Task did not complete within 120s.
Session ID: abc-123
Steps completed before timeout: 4
  - Navigate to https://example.com
  - Click search button`}
            </pre>
          </div>
        </div>
      </DocSection>

      <DocSection title="list_learned_skills" delay={80}>
        <div className="border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 bg-surface/40 border-b border-border">
            <span className="font-mono text-[11px] text-text-muted font-medium">Example output</span>
          </div>
          <pre className="p-4 font-mono text-[11px] text-text-dim leading-[1.7] overflow-x-auto">
{`Learned Skills (3 total):

1. amazon.com — "Search for {{query}} on Amazon"
   Confidence: 89% | Steps: 4 rocket + 3 agent
   Avg speedup: 4.2x | Used 7 times (6 success)

2. github.com — "Go to trending and extract top repos"
   Confidence: 95% | Steps: 3 rocket + 2 agent
   Avg speedup: 6.1x | Used 12 times (12 success)

3. news.ycombinator.com — "Get the top story"
   Confidence: 79% | Steps: 9 rocket + 1 agent
   Avg speedup: 5.4x | Used 2 times (2 success)`}
          </pre>
        </div>
      </DocSection>

      <DocSection title="SessionStatus (for HTTP API users)" delay={120}>
        <p className="text-[12px] text-text-muted leading-relaxed mb-3">
          The MCP server polls this internally. Only relevant if you're calling the HTTP API directly.
        </p>
        <div className="rounded-xl border border-border overflow-hidden">
          <table className="w-full text-[11px] font-mono">
            <tbody className="divide-y divide-border">
              {[
                ['session_id', 'string', 'Unique run identifier'],
                ['status', 'pending | running | complete | error', ''],
                ['phase', 'idle | rocket | agent | learning', 'Current execution phase'],
                ['mode_used', 'rocket | baseline_learn', 'Which path was taken'],
                ['duration_ms', 'number', 'Total elapsed time'],
                ['steps', 'StepInfo[]', 'Each step with type, description, duration'],
                ['result', 'string | null', "Agent's final answer"],
                ['live_url', 'string | null', 'Watch the browser live'],
                ['template_match', '{ similarity, domain }', 'Match details if found'],
              ].map(([field, type, note]) => (
                <tr key={field} className="hover:bg-white/[0.02]">
                  <td className="px-3 py-2 text-lime/90 w-32 align-top">{field}</td>
                  <td className="px-3 py-2 text-sky/70 align-top">{type}</td>
                  <td className="px-3 py-2 text-text-muted align-top font-sans text-[12px]">{note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DocSection>
    </DocPageShell>
  );
}
