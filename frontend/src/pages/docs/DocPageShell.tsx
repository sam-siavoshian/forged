import type { ReactNode } from 'react';

const stagger = (ms: number) => ({ animationDelay: `${ms}ms` } as const);

export function DocPageShell({
  title,
  kicker,
  children,
}: {
  title: string;
  kicker?: string;
  children: ReactNode;
}) {
  return (
    <div className="relative">
      <div
        className="pointer-events-none absolute -top-8 -right-12 w-[min(50vw,380px)] h-[min(50vw,380px)] rounded-full opacity-[0.05]"
        style={{
          background: 'radial-gradient(circle at 35% 35%, rgba(200,255,0,0.4) 0%, transparent 58%)',
        }}
      />
      <header className="mb-8 md:mb-10 anim-fade-up relative border-b border-border/50 pb-8">
        {kicker && (
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-text-muted mb-2">{kicker}</p>
        )}
        <h1 className="text-[1.375rem] sm:text-[1.5rem] font-semibold text-text leading-snug tracking-[-0.02em]">
          {title}
        </h1>
      </header>
      <div className="relative space-y-0 text-[14px] leading-[1.65] text-text-dim">{children}</div>
    </div>
  );
}

export function DocSection({
  title,
  children,
  delay = 0,
}: {
  title: string;
  children: ReactNode;
  delay?: number;
}) {
  return (
    <section className="mb-10 md:mb-12 last:mb-0 anim-fade-up" style={stagger(delay)}>
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-text-muted mb-3">{title}</h2>
      {children}
    </section>
  );
}
