import { useEffect, useState } from 'react';
import { getRaceHistory, type RaceHistoryEntry } from '../api';

export function BenchmarksPage() {
  const [races, setRaces] = useState<RaceHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRaceHistory()
      .then(setRaces)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // ── Aggregate stats ──
  const wins = races.filter(r => r.speedup > 1);
  const losses = races.filter(r => r.speedup <= 1);
  const winRate = races.length > 0 ? (wins.length / races.length) * 100 : 0;

  const avgSpeedup = races.length > 0
    ? races.reduce((sum, r) => sum + r.speedup, 0) / races.length
    : 0;
  const bestSpeedup = races.length > 0
    ? Math.max(...races.map(r => r.speedup))
    : 0;

  const totalTimeSavedMs = races.reduce(
    (sum, r) => sum + Math.max(0, r.baseline_duration_ms - r.rocket_duration_ms), 0,
  );

  const avgBaselineMs = races.length > 0
    ? races.reduce((sum, r) => sum + r.baseline_duration_ms, 0) / races.length
    : 0;
  const avgForgeMs = races.length > 0
    ? races.reduce((sum, r) => sum + r.rocket_duration_ms, 0) / races.length
    : 0;

  const totalForgedSteps = races.reduce((sum, r) => sum + (r.rocket_steps ?? 0), 0);

  // Cost estimate: ~$0.003 per agent step (Claude Sonnet screenshot + reasoning)
  const avgBaselineSteps = races.length > 0
    ? races.reduce((sum, r) => {
        const baselineSteps = Math.ceil(r.baseline_duration_ms / 3000);
        return sum + baselineSteps;
      }, 0) / races.length
    : 0;
  const avgForgeAgentSteps = races.length > 0
    ? races.reduce((sum, r) => {
        const forgeSteps = r.rocket_steps ?? 0;
        // Agent only runs for the non-forged portion
        const agentTimeMs = r.rocket_duration_ms - (forgeSteps * 200); // ~200ms per PW step
        const agentSteps = Math.max(1, Math.ceil(agentTimeMs / 3000));
        return sum + agentSteps;
      }, 0) / races.length
    : 0;
  const costReduction = avgBaselineSteps > 0
    ? ((1 - avgForgeAgentSteps / avgBaselineSteps) * 100)
    : 0;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-muted mb-2">
            Performance
          </p>
          <h1 className="text-[28px] font-serif italic text-text">Benchmarks</h1>
          <p className="text-[13px] text-text-dim mt-2">
            Every race is recorded. See how Forge compares to vanilla browser-use over time.
          </p>
        </div>

        {races.length > 0 && (
          <>
            {/* Hero stat */}
            <div
              className="rounded-2xl px-6 py-6 mb-6 text-center"
              style={{
                background: 'rgba(200,255,0,0.02)',
                border: '1px solid rgba(200,255,0,0.1)',
                boxShadow: 'inset 0 4px 12px rgba(0,0,0,0.35), inset 0 -2px 6px rgba(255,255,255,0.02), 0 1px 0 rgba(255,255,255,0.03)',
              }}
            >
              <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-muted mb-3">
                Forge vs browser-use
              </p>
              <p className="font-serif italic text-[56px] leading-none text-lime tracking-tight">
                {avgSpeedup.toFixed(1)}x
              </p>
              <p className="text-[12px] text-text-dim mt-3">
                average faster across {races.length} race{races.length !== 1 ? 's' : ''}
              </p>
            </div>

            {/* Primary stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <StatCard label="Win rate" value={`${winRate.toFixed(0)}%`} sub={`${wins.length}W / ${losses.length}L`} accent />
              <StatCard label="Best run" value={`${bestSpeedup.toFixed(1)}x`} sub="peak speedup" accent />
              <StatCard label="Time saved" value={formatDuration(totalTimeSavedMs)} sub="total across all" />
              <StatCard label="Races" value={`${races.length}`} sub="completed" />
            </div>

            {/* Detailed breakdown */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-8">
              <StatCard label="Avg browser-use" value={`${(avgBaselineMs / 1000).toFixed(1)}s`} sub="vanilla agent" />
              <StatCard label="Avg Forge" value={`${(avgForgeMs / 1000).toFixed(1)}s`} sub="forged + agent" accent />
              <StatCard label="Forged steps" value={`${totalForgedSteps}`} sub={`0 LLM calls (${totalForgedSteps > 0 ? '~' + (totalForgedSteps * 0.2).toFixed(0) + 's' : '0s'} total)`} accent />
            </div>

            {/* LLM cost insight */}
            {costReduction > 5 && (
              <div
                className="rounded-xl px-4 py-3 mb-8 flex items-center gap-3"
                style={{
                  background: 'rgba(0,0,0,0.15)',
                  border: '1px solid rgba(255,255,255,0.04)',
                  boxShadow: 'inset 0 2px 6px rgba(0,0,0,0.3), 0 1px 0 rgba(255,255,255,0.02)',
                }}
              >
                <span className="text-[18px]">$</span>
                <div>
                  <p className="text-[12px] text-text-dim">
                    Forge skips <span className="text-lime font-mono font-medium">~{costReduction.toFixed(0)}%</span> of LLM calls
                    by replaying forged steps via Playwright instead of reasoning through them.
                  </p>
                  <p className="text-[10px] text-text-muted mt-0.5">
                    {totalForgedSteps} steps at ~$0.003/step = ~${(totalForgedSteps * 0.003).toFixed(2)} saved in API costs
                  </p>
                </div>
              </div>
            )}
          </>
        )}

        {/* Race list */}
        {loading && (
          <div className="text-center py-12">
            <p className="text-[13px] text-text-muted">Loading race history...</p>
          </div>
        )}

        {!loading && races.length === 0 && (
          <div className="saas-inset-sm rounded-2xl px-8 py-10 text-center">
            <p className="text-[14px] text-text-dim mb-1">No races yet</p>
            <p className="text-[12px] text-text-muted">
              Run a Race to see benchmark results here.
            </p>
          </div>
        )}

        {!loading && races.length > 0 && (
          <>
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted mb-3">
              Race history
            </p>
            <div className="flex flex-col gap-2">
              {races.map((race, i) => (
                <RaceRow key={`${race.created_at}-${i}`} race={race} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(0)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = Math.round((ms % 60000) / 1000);
  return `${mins}m ${secs}s`;
}

function StatCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div
      className="rounded-xl px-4 py-3"
      style={{
        background: 'rgba(0,0,0,0.2)',
        border: '1px solid rgba(255,255,255,0.04)',
        boxShadow: 'inset 0 4px 10px rgba(0,0,0,0.4), inset 0 1px 3px rgba(0,0,0,0.25), inset 0 -1px 3px rgba(255,255,255,0.015), 0 1px 0 rgba(255,255,255,0.03)',
      }}
    >
      <p className="text-[9px] font-mono uppercase tracking-[0.16em] text-text-muted">{label}</p>
      <p className={`text-[22px] font-serif italic mt-1 ${accent ? 'text-lime' : 'text-text'}`}>{value}</p>
      {sub && <p className="text-[9px] text-text-muted mt-0.5">{sub}</p>}
    </div>
  );
}

function RaceRow({ race }: { race: RaceHistoryEntry }) {
  const baselineSec = (race.baseline_duration_ms / 1000).toFixed(1);
  const rocketSec = (race.rocket_duration_ms / 1000).toFixed(1);
  const barRatio = race.rocket_duration_ms / race.baseline_duration_ms;
  const timeSaved = ((race.baseline_duration_ms - race.rocket_duration_ms) / 1000).toFixed(1);
  const date = new Date(race.created_at);
  const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  const won = race.speedup > 1;

  return (
    <div
      className="saas-card px-4 py-3.5"
      style={{ borderColor: won ? 'rgba(200,255,0,0.08)' : 'rgba(255,107,53,0.08)' }}
    >
      <div className="flex items-start justify-between gap-4 mb-3">
        <p className="text-[12px] text-text-dim leading-snug flex-1 line-clamp-2">
          {race.task}
        </p>
        <div className="flex items-center gap-2 shrink-0">
          {race.rocket_steps != null && race.rocket_steps > 0 && (
            <span className="text-[9px] font-mono text-text-muted bg-white/[0.03] px-1.5 py-0.5 rounded">
              {race.rocket_steps} PW
            </span>
          )}
          <span className={`font-serif italic text-[20px] leading-none ${won ? 'text-lime' : 'text-amber'}`}>
            {race.speedup.toFixed(1)}x
          </span>
        </div>
      </div>

      {/* Bars */}
      <div className="space-y-1.5 mb-2.5">
        <div className="flex items-center gap-2.5">
          <span className="w-10 text-right font-mono text-[10px] text-text-muted tabular-nums">{baselineSec}s</span>
          <div
            className="flex-1 h-2 rounded-md overflow-hidden"
            style={{
              background: 'rgba(0,0,0,0.25)',
              boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.3)',
            }}
          >
            <div
              className="h-full rounded-md"
              style={{
                width: '100%',
                background: 'linear-gradient(90deg, rgba(255,107,53,0.2), rgba(255,107,53,0.05))',
              }}
            />
          </div>
          <span className="w-12 text-[9px] text-text-muted">Without</span>
        </div>
        <div className="flex items-center gap-2.5">
          <span className="w-10 text-right font-mono text-[10px] text-lime font-medium tabular-nums">{rocketSec}s</span>
          <div
            className="flex-1 h-2 rounded-md overflow-hidden"
            style={{
              background: 'rgba(0,0,0,0.25)',
              boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.3)',
            }}
          >
            <div
              className="h-full rounded-md"
              style={{
                width: `${Math.max(barRatio * 100, 4)}%`,
                background: 'linear-gradient(90deg, rgba(200,255,0,0.35), rgba(200,255,0,0.1))',
              }}
            />
          </div>
          <span className="w-12 text-[9px] text-lime">Forged</span>
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px] text-text-muted">
        <span>{dateStr} at {timeStr}</span>
        <span className={`font-mono ${won ? 'text-lime/60' : 'text-amber/60'}`}>
          {won ? `${timeSaved}s saved` : `${Math.abs(Number(timeSaved))}s slower`}
        </span>
      </div>
    </div>
  );
}
