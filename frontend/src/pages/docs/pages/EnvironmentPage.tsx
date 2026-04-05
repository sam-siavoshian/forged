import { DocPageShell, DocSection } from '../DocPageShell';

export function EnvironmentPage() {
  return (
    <DocPageShell kicker="Reference" title="Configuration">
      <DocSection title="Supported clients" delay={40}>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { label: 'Claude Code', desc: 'Full MCP support via CLI' },
            { label: 'Cursor', desc: 'MCP server integration' },
            { label: 'Windsurf', desc: 'MCP-compatible assistant' },
          ].map(({ label, desc }) => (
            <div key={label} className="border border-border rounded-lg p-3 bg-surface/30">
              <p className="text-[13px] text-text font-medium mb-0.5">{label}</p>
              <p className="text-[11px] text-text-muted">{desc}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[12px] text-text-muted leading-relaxed">
          Any AI assistant that supports the Model Context Protocol can connect to Forged.
        </p>
      </DocSection>

      <DocSection title="How it connects" delay={80}>
        <div className="rounded-xl border border-border overflow-hidden bg-surface/20">
          <div className="px-4 py-4 font-mono text-[12px] text-text-dim leading-[2] text-center">
            <span className="text-text font-medium">Your AI assistant</span>
            <span className="text-text-muted mx-2">&rarr;</span>
            <span className="text-lime font-medium">Forged MCP</span>
            <span className="text-text-muted mx-2">&rarr;</span>
            <span className="text-sky/90 font-medium">Forged API</span>
            <span className="text-text-muted mx-2">&rarr;</span>
            <span className="text-amber-400 font-medium">Cloud Browser</span>
          </div>
        </div>
        <p className="mt-3 text-[13px] text-text-dim leading-relaxed">
          The MCP server is a lightweight proxy. It translates tool calls into HTTP requests
          to the Forged API, which manages browser sessions, template matching, and learning.
        </p>
      </DocSection>

      <DocSection title="Confidence bands" delay={120}>
        <p className="text-[13px] text-text-dim leading-relaxed mb-3">
          Template matching uses pgvector similarity search with these confidence thresholds:
        </p>
        <div className="rounded-xl border border-border overflow-hidden">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-border bg-surface/40">
                <th className="px-3 py-2 text-left font-mono text-[10px] text-text-muted uppercase tracking-wider">Band</th>
                <th className="px-3 py-2 text-left font-mono text-[10px] text-text-muted uppercase tracking-wider">Similarity</th>
                <th className="px-3 py-2 text-left font-mono text-[10px] text-text-muted uppercase tracking-wider">Behavior</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono text-[11px]">
              <tr className="hover:bg-white/[0.02]">
                <td className="px-3 py-2.5 text-lime">Very High</td>
                <td className="px-3 py-2.5 text-text-dim">&ge; 90%</td>
                <td className="px-3 py-2.5 text-text-muted font-sans text-[12px]">Execute all rocket steps immediately</td>
              </tr>
              <tr className="hover:bg-white/[0.02]">
                <td className="px-3 py-2.5 text-lime/80">High</td>
                <td className="px-3 py-2.5 text-text-dim">75 – 89%</td>
                <td className="px-3 py-2.5 text-text-muted font-sans text-[12px]">Execute rocket steps</td>
              </tr>
              <tr className="hover:bg-white/[0.02]">
                <td className="px-3 py-2.5 text-amber-400">Medium</td>
                <td className="px-3 py-2.5 text-text-dim">50 – 74%</td>
                <td className="px-3 py-2.5 text-text-muted font-sans text-[12px]">LLM verifies match before executing</td>
              </tr>
              <tr className="hover:bg-white/[0.02]">
                <td className="px-3 py-2.5 text-text-muted">No match</td>
                <td className="px-3 py-2.5 text-text-dim">&lt; 50%</td>
                <td className="px-3 py-2.5 text-text-muted font-sans text-[12px]">Full agent, auto-learn template</td>
              </tr>
            </tbody>
          </table>
        </div>
      </DocSection>

      <DocSection title="Step classification" delay={160}>
        <p className="text-[13px] text-text-dim leading-relaxed mb-3">
          When Forged learns a template, each step is classified:
        </p>
        <div className="space-y-2">
          {[
            { label: 'FIXED', color: 'lime', desc: 'Same action and target every time. Replayed via Playwright.' },
            { label: 'PARAMETERIZED', color: 'amber-400', desc: 'Same action, different value. E.g. search input with varying queries.' },
            { label: 'DYNAMIC', color: 'sky', desc: 'Requires reasoning. Handled by the AI agent at runtime.' },
          ].map(({ label, color, desc }) => (
            <div key={label} className="flex gap-3 items-start">
              <span className={`font-mono text-[11px] text-${color} shrink-0 w-28 pt-0.5 font-medium`}>{label}</span>
              <p className="text-[13px] text-text-dim leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </DocSection>
    </DocPageShell>
  );
}
