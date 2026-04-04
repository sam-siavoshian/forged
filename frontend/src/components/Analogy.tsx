const REAPER_IMG = '/reaper.jpg';
const SHAHED_IMG = '/shahed.jpg';

export function Analogy() {
  return (
    <div className="w-full max-w-[600px]">
      <p className="text-[10px] font-mono uppercase tracking-[0.25em] text-text-muted text-center mb-4">
        The principle
      </p>

      <div className="rounded-2xl border border-border overflow-hidden bg-surface">
        {/* ── Drone images ── */}
        <div className="grid grid-cols-[1fr_1px_1fr]">
          {/* Reaper */}
          <div className="relative overflow-hidden" style={{ background: '#0d0d0d' }}>
            <img
              src={REAPER_IMG}
              alt="MQ-9 Reaper drone"
              className="w-full h-[140px] object-cover opacity-40"
              loading="lazy"
            />
            {/* Amber tint overlay */}
            <div className="absolute inset-0" style={{ background: 'linear-gradient(to bottom, rgba(255,107,53,0.06), rgba(10,10,10,0.85))' }} />
            {/* Label on image */}
            <div className="absolute bottom-3 left-4 right-4">
              <p className="text-[10px] font-mono text-amber uppercase tracking-[0.15em] mb-1">The complex way</p>
              <p className="font-serif italic text-[32px] leading-none text-text-dim tracking-tight">$32M</p>
            </div>
          </div>

          <div className="bg-border" />

          {/* Shahed */}
          <div className="relative overflow-hidden" style={{ background: '#0d0d0d' }}>
            <img
              src={SHAHED_IMG}
              alt="Shahed-136 drone with rocket booster"
              className="w-full h-[140px] object-cover opacity-40"
              loading="lazy"
            />
            {/* Lime tint overlay */}
            <div className="absolute inset-0" style={{ background: 'linear-gradient(to bottom, rgba(200,255,0,0.04), rgba(10,10,10,0.85))' }} />
            {/* Label on image */}
            <div className="absolute bottom-3 left-4 right-4">
              <p className="text-[10px] font-mono text-lime uppercase tracking-[0.15em] mb-1">The smart way</p>
              <p className="font-serif italic text-[32px] leading-none text-lime tracking-tight">$20K</p>
            </div>
          </div>
        </div>

        {/* ── Drone details ── */}
        <div className="grid grid-cols-[1fr_1px_1fr] border-t border-border">
          <div className="px-4 py-3">
            <p className="text-[12px] text-text-dim font-medium">MQ-9 Reaper</p>
            <p className="text-[11px] text-text-muted/60 mt-0.5 leading-relaxed">
              5,000 lbs. Satellite uplink. Ground crew of 180.
            </p>
          </div>
          <div className="bg-border" />
          <div className="px-4 py-3">
            <p className="text-[12px] text-text font-medium">Shahed-136</p>
            <p className="text-[11px] text-text-muted/60 mt-0.5 leading-relaxed">
              Simple airframe + rocket booster. Same mission. Done.
            </p>
          </div>
        </div>

        {/* ── Arrow transition ── */}
        <div className="flex items-center justify-center h-8 border-t border-border" style={{ background: 'rgba(200,255,0,0.015)' }}>
          <div className="flex items-center gap-3 text-[10px] font-mono text-text-muted uppercase tracking-[0.2em]">
            <div className="w-8 h-px bg-border" />
            Now apply this to browser agents
            <div className="w-8 h-px bg-border" />
          </div>
        </div>

        {/* ── Browser agent comparison ── */}
        <div className="grid grid-cols-[1fr_1px_1fr] border-t border-border">
          {/* Vanilla agent */}
          <div className="p-4">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[24px] font-semibold text-text-dim tabular-nums">~40s</span>
              <span className="text-[11px] text-text-muted">per task</span>
            </div>
            <p className="text-[12px] text-text-muted mt-1">Vanilla browser-use agent</p>
            <p className="text-[11px] text-text-muted/60 mt-0.5">
              Thinks through every click. Every single time.
            </p>
          </div>

          <div className="bg-border relative">
            <span
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[10px] font-mono text-text-muted px-1.5 py-0.5 rounded"
              style={{ background: '#111111' }}
            >
              vs
            </span>
          </div>

          {/* Boosted agent */}
          <div className="p-4">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[24px] font-semibold text-lime tabular-nums">~8s</span>
              <span className="text-[11px] text-lime/60">per task</span>
            </div>
            <p className="text-[12px] text-text mt-1">Agent + Rocket Booster</p>
            <p className="text-[11px] text-text-muted/60 mt-0.5">
              Playwright replays the known. Agent handles the new.
            </p>
          </div>
        </div>

        {/* ── Punchline ── */}
        <div className="border-t border-border px-5 py-3.5 text-center" style={{ background: 'rgba(200,255,0,0.02)' }}>
          <p className="text-[13px] text-text-dim">
            Same task. <span className="text-lime font-mono font-medium">5x faster.</span>{' '}
            You don't need a better agent — you need a{' '}
            <span className="text-lime italic font-serif">booster.</span>
          </p>
        </div>
      </div>
    </div>
  );
}
