import { useEffect, useState } from 'react';

const REAPER_IMG = '/reaper.jpg';
const SHAHED_IMG = '/shahed.jpg';

export function Analogy() {
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setAnimate(true), 600);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="w-full max-w-[680px]">
      <div className="rounded-2xl border border-border overflow-hidden" style={{ background: '#0e0e0e' }}>

        {/* ── Top: Drone comparison with images ── */}
        <div className="grid grid-cols-[1fr_1px_1fr]">
          <div className="relative overflow-hidden h-[120px]">
            <img src={REAPER_IMG} alt="MQ-9 Reaper" className="w-full h-full object-cover opacity-30" loading="lazy" />
            <div className="absolute inset-0" style={{ background: 'linear-gradient(135deg, rgba(255,107,53,0.08), rgba(10,10,10,0.9))' }} />
            <div className="absolute inset-0 flex items-end p-4">
              <div>
                <p className="text-[9px] font-mono text-amber uppercase tracking-[0.2em] mb-0.5">Complex</p>
                <p className="font-serif italic text-[28px] leading-none text-text-dim">$32M</p>
                <p className="text-[11px] text-text-muted mt-0.5">MQ-9 Reaper &middot; 5,000 lbs &middot; crew of 180</p>
              </div>
            </div>
          </div>

          <div style={{ background: '#1a1a1a' }} />

          <div className="relative overflow-hidden h-[120px]">
            <img src={SHAHED_IMG} alt="Shahed-136" className="w-full h-full object-cover opacity-30" loading="lazy" />
            <div className="absolute inset-0" style={{ background: 'linear-gradient(135deg, rgba(200,255,0,0.05), rgba(10,10,10,0.9))' }} />
            <div className="absolute inset-0 flex items-end p-4">
              <div>
                <p className="text-[9px] font-mono text-lime uppercase tracking-[0.2em] mb-0.5">Simple + booster</p>
                <p className="font-serif italic text-[28px] leading-none text-lime">$20K</p>
                <p className="text-[11px] text-text-dim mt-0.5">Shahed-136 &middot; rocket booster &middot; same mission</p>
              </div>
            </div>
          </div>
        </div>

        {/* ── Speed race visualization ── */}
        <div className="px-5 py-4 border-t border-border">
          <div className="flex items-center gap-3 text-[10px] font-mono text-text-muted uppercase tracking-[0.15em] mb-3">
            <div className="w-4 h-px bg-border" />
            Apply this to browser agents
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Animated race bars */}
          <div className="space-y-2">
            {/* Baseline — slow */}
            <div className="flex items-center gap-3">
              <span className="w-12 text-right font-mono text-[13px] text-text-muted tabular-nums">~40s</span>
              <div className="flex-1 h-3 rounded-full overflow-hidden" style={{ background: '#161616' }}>
                <div
                  className="h-full rounded-full origin-left"
                  style={{
                    width: '100%',
                    background: 'linear-gradient(90deg, rgba(255,107,53,0.3), rgba(255,107,53,0.08))',
                    transform: animate ? 'scaleX(1)' : 'scaleX(0)',
                    transition: 'transform 3s cubic-bezier(0.1, 0, 0.3, 1)',
                  }}
                />
              </div>
              <span className="w-14 text-[10px] text-text-muted">Vanilla</span>
            </div>

            {/* Rocket — fast (shoots across then stops at ~20%) */}
            <div className="flex items-center gap-3">
              <span className="w-12 text-right font-mono text-[13px] text-lime font-medium tabular-nums">~8s</span>
              <div className="flex-1 h-3 rounded-full overflow-hidden" style={{ background: '#161616' }}>
                <div
                  className="h-full rounded-full origin-left"
                  style={{
                    width: '20%',
                    background: 'linear-gradient(90deg, rgba(200,255,0,0.5), rgba(200,255,0,0.15))',
                    transform: animate ? 'scaleX(1)' : 'scaleX(0)',
                    transition: 'transform 0.4s cubic-bezier(0.16, 1, 0.3, 1) 0.2s',
                    boxShadow: animate ? '0 0 12px rgba(200,255,0,0.2)' : 'none',
                  }}
                />
              </div>
              <span className="w-14 text-[10px] text-lime">Boosted</span>
            </div>
          </div>
        </div>

        {/* ── Punchline ── */}
        <div className="px-5 py-3 border-t border-border text-center" style={{ background: 'rgba(200,255,0,0.015)' }}>
          <p className="text-[12px] text-text-dim">
            Same task. <span className="text-lime font-mono font-medium">5x faster.</span>{' '}
            You don't need a better agent — you need a{' '}
            <span className="text-lime italic font-serif">booster.</span>
          </p>
        </div>
      </div>
    </div>
  );
}
