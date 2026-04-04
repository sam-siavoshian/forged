/**
 * Architecture — system flowchart with SVG wiring.
 * Uses a fixed 600px canvas centered in its container so coordinates are stable.
 */

export function Architecture() {
  // All coordinates assume a 600 x 400 canvas
  const W = 600;
  const H = 400;

  return (
    <div className="w-full max-w-[660px]">
      <p className="text-[10px] font-mono uppercase tracking-[0.25em] text-text-muted text-center mb-5">
        How it works
      </p>

      {/* Fixed-size canvas, centered */}
      <div className="flex justify-center">
        <div className="relative" style={{ width: W, height: H }}>

          {/* ═══ SVG WIRES ═══ */}
          <svg className="absolute inset-0" width={W} height={H} viewBox={`0 0 ${W} ${H}`} fill="none" style={{ zIndex: 0 }}>
            {/* Task → diamond */}
            <line x1="300" y1="38" x2="300" y2="72" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />

            {/* Diamond → YES left */}
            <line x1="255" y1="96" x2="150" y2="96" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />
            <line x1="150" y1="96" x2="150" y2="140" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />

            {/* Diamond → NO right */}
            <line x1="345" y1="96" x2="450" y2="96" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />
            <line x1="450" y1="96" x2="450" y2="140" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />

            {/* Rocket → merge */}
            <line x1="150" y1="218" x2="150" y2="248" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />
            <line x1="150" y1="248" x2="300" y2="248" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />
            <line x1="300" y1="248" x2="300" y2="264" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />

            {/* Full agent → merge */}
            <line x1="450" y1="218" x2="450" y2="248" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />
            <line x1="450" y1="248" x2="300" y2="248" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />

            {/* Handoff → result */}
            <line x1="300" y1="326" x2="300" y2="352" stroke="rgba(85,85,85,0.3)" strokeWidth="1" />

            {/* Learning loop (dashed) */}
            <path
              d="M 220 368 L 46 368 L 46 96 L 90 96"
              stroke="rgba(251,191,36,0.25)"
              strokeWidth="1"
              strokeDasharray="4 3"
            />

            {/* Labels on wires */}
            <text x="178" y="89" fill="rgba(200,255,0,0.5)" fontSize="9" fontFamily="monospace">YES</text>
            <text x="370" y="89" fill="rgba(255,100,100,0.4)" fontSize="9" fontFamily="monospace">NO</text>
            <text x="16" y="240" fill="rgba(251,191,36,0.25)" fontSize="8" fontFamily="monospace" transform="rotate(-90, 30, 235)">learn loop</text>
          </svg>

          {/* ═══ NODES ═══ */}

          {/* Task */}
          <N left={225} top={6} w={150} h={32}>
            <span className="text-[9px] font-mono text-text-muted">user task</span>
            <span className="text-[10px] text-text">&quot;Search for X on Amazon&quot;</span>
          </N>

          {/* Diamond */}
          <div className="absolute" style={{ left: 256, top: 68, zIndex: 1 }}>
            <div className="w-[88px] h-[48px] flex items-center justify-center"
              style={{
                background: '#111',
                border: '1px solid rgba(200,255,0,0.15)',
                clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)',
              }}
            >
              <span className="text-[8px] font-mono text-lime/70 text-center leading-tight">template<br />exists?</span>
            </div>
          </div>

          {/* LEFT: Rocket */}
          <N left={66} top={140} w={168} h={78} border="rgba(200,255,0,0.12)">
            <span className="text-[8px] font-mono text-lime/50 tracking-widest">PLAYWRIGHT ROCKET</span>
            <span className="text-[10px] text-text-dim mt-1">Replays known steps via CDP</span>
            <span className="text-[9px] text-text-muted mt-0.5">navigate, click, fill, press</span>
            <span className="text-[8px] font-mono text-lime/40 mt-1">~200ms/step &middot; 0 LLM calls</span>
          </N>

          {/* Tech label */}
          <span className="absolute text-[7px] font-mono text-text-muted/25" style={{ left: 100, top: 130, zIndex: 2 }}>Playwright + CDP</span>

          {/* RIGHT: Full Agent */}
          <N left={366} top={140} w={168} h={78} border="rgba(255,100,100,0.08)">
            <span className="text-[8px] font-mono text-red-400/40 tracking-widest">FULL AGENT</span>
            <span className="text-[10px] text-text-dim mt-1">No template. LLM every step.</span>
            <span className="text-[9px] text-text-muted mt-0.5">reason, act, observe, repeat</span>
            <span className="text-[8px] font-mono text-red-400/30 mt-1">~3s/step &middot; expensive</span>
          </N>

          <span className="absolute text-[7px] font-mono text-text-muted/25" style={{ left: 410, top: 130, zIndex: 2 }}>browser-use</span>

          {/* CENTER: Agent handoff */}
          <N left={200} top={264} w={200} h={62} border="rgba(56,189,248,0.12)">
            <span className="text-[8px] font-mono text-sky/50 tracking-widest">AGENT HANDOFF</span>
            <span className="text-[10px] text-text-dim mt-1">Claude takes over at handoff point</span>
            <span className="text-[9px] text-text-muted mt-0.5">Only dynamic steps (decisions)</span>
          </N>

          <span className="absolute text-[7px] font-mono text-text-muted/25" style={{ left: 255, top: 254, zIndex: 2 }}>Claude Sonnet 4.6</span>

          {/* Result + learn */}
          <div className="absolute flex items-center gap-2" style={{ left: 160, top: 350, zIndex: 1 }}>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border" style={{ background: '#0d0d0d', borderColor: '#222' }}>
              <div className="w-1.5 h-1.5 rounded-full bg-lime" />
              <span className="text-[9px] text-text-dim">Result</span>
            </div>
            <svg width="16" height="10" viewBox="0 0 16 10" fill="none">
              <path d="M1 5h12M10 1.5l3.5 3.5-3.5 3.5" stroke="rgba(251,191,36,0.3)" strokeWidth="1" strokeLinecap="round" />
            </svg>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border" style={{ background: 'rgba(251,191,36,0.03)', borderColor: 'rgba(251,191,36,0.12)' }}>
              <div className="w-1.5 h-1.5 rounded-full bg-amber-400/50" />
              <span className="text-[9px] text-amber-400/60 font-mono">extract_template → supabase</span>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function N({
  left, top, w, h, border, children,
}: {
  left: number; top: number; w: number; h: number;
  border?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="absolute flex flex-col items-center justify-center text-center px-3"
      style={{
        left, top, width: w, height: h,
        background: '#0e0e0e',
        border: `1px solid ${border || 'rgba(100,100,100,0.15)'}`,
        borderRadius: 8,
        zIndex: 1,
      }}
    >
      {children}
    </div>
  );
}
