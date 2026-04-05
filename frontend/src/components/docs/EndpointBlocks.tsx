export function MethodBadge({ method }: { method: 'GET' | 'POST' | 'DELETE' }) {
  const cls =
    method === 'GET'
      ? 'bg-sky/10 text-sky border-sky/20'
      : method === 'DELETE'
        ? 'bg-red-400/10 text-red-400 border-red-400/20'
        : 'bg-lime/10 text-lime border-lime/20';
  return (
    <span className={`inline-flex font-mono text-[10px] font-semibold px-2 py-0.5 rounded-md border ${cls}`}>
      {method}
    </span>
  );
}

export function EndpointRow({
  method,
  path,
  res,
  note,
}: {
  method: 'GET' | 'POST' | 'DELETE';
  path: string;
  res: string;
  note: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5 border-b border-border bg-black/15">
        <MethodBadge method={method} />
        <code className="font-mono text-[12px] md:text-[13px] text-text tracking-tight">{path}</code>
      </div>
      <div className="px-3 py-2.5 space-y-2">
        <p className="text-[11px] font-mono uppercase tracking-[0.12em] text-text-muted">Response</p>
        <p className="font-mono text-[11px] md:text-[12px] text-sky/85 break-words leading-relaxed">{res}</p>
        <p className="text-[13px] text-text-dim leading-relaxed pt-1">{note}</p>
      </div>
    </div>
  );
}
