import { useEffect } from 'react';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import { SearchIcon } from 'lucide-animated';
import { DOC_SEARCH_INDEX } from '../../docs/searchIndex';

export function DocsCommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, [open, onOpenChange]);

  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false);
    };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [open, onOpenChange]);

  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[8vh] sm:pt-[12vh] px-3 sm:px-4 pb-8"
      role="dialog"
      aria-modal="true"
      aria-label="Search documentation"
    >
      {/* Linear-style: dim backdrop, click to close */}
      <button
        type="button"
        aria-label="Close search"
        className="fixed inset-0 bg-black/60 backdrop-blur-[3px] animate-[fade-in_0.1s_ease-out]"
        onClick={() => onOpenChange(false)}
      />

      <Command
        loop
        className="relative z-10 flex w-full max-w-[500px] flex-col overflow-hidden rounded-lg border border-border bg-surface shadow-[0_0_0_1px_rgba(255,255,255,0.03),0_16px_48px_-8px_rgba(0,0,0,0.65)] animate-[scale-up_0.14s_cubic-bezier(0.16,1,0.3,1)] max-h-[min(480px,70vh)] [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.08em] [&_[cmdk-group-heading]]:text-text-muted"
      >
        {/* Search field — compact strip */}
        <div className="flex items-center gap-2 border-b border-border px-3 py-2 shrink-0">
          <SearchIcon size={16} className="shrink-0 text-text-muted" aria-hidden />
          <Command.Input
            placeholder="Search documentation…"
            autoFocus
            className="flex-1 min-w-0 bg-transparent text-[13px] leading-snug text-text placeholder:text-text-muted outline-none py-0.5"
          />
          <kbd className="hidden sm:inline-flex shrink-0 items-center rounded-md border border-border/80 bg-black/35 px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
            ESC
          </kbd>
        </div>

        <Command.List className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-1.5 outline-none scroll-py-1">
          <Command.Empty className="py-10 text-center text-[13px] text-text-muted">
            No results.
          </Command.Empty>
          <Command.Group heading="Documentation">
            {DOC_SEARCH_INDEX.map((item) => (
              <Command.Item
                key={item.id}
                value={`${item.title} ${item.keywords.join(' ')}`}
                onSelect={() => {
                  navigate(item.path);
                  onOpenChange(false);
                }}
                className="flex cursor-pointer flex-col gap-0.5 rounded-md px-2 py-1.5 text-left outline-none data-[selected=true]:bg-white/[0.06] data-[selected=true]:text-text"
              >
                <span className="text-[13px] font-medium text-text">{item.title}</span>
                <span className="truncate font-mono text-[11px] text-text-muted">{item.path}</span>
              </Command.Item>
            ))}
          </Command.Group>
        </Command.List>

        <div className="flex shrink-0 items-center justify-between gap-2 border-t border-border/80 bg-black/25 px-3 py-1.5">
          <p className="text-[11px] text-text-muted">
            <kbd className="rounded border border-border/60 bg-black/30 px-1 py-px font-mono text-[10px]">↑</kbd>
            <kbd className="ml-1 rounded border border-border/60 bg-black/30 px-1 py-px font-mono text-[10px]">↓</kbd>
            <span className="ml-1.5">to navigate</span>
            <span className="mx-2 text-border">·</span>
            <kbd className="rounded border border-border/60 bg-black/30 px-1 py-px font-mono text-[10px]">↵</kbd>
            <span className="ml-1">to open</span>
          </p>
          <p className="hidden sm:block text-[11px] text-text-muted/80">
            <kbd className="rounded border border-border/50 bg-black/25 px-1.5 py-0.5 font-mono text-[10px]">⌘</kbd>
            <kbd className="ml-0.5 rounded border border-border/50 bg-black/25 px-1.5 py-0.5 font-mono text-[10px]">K</kbd>
            <span className="ml-1.5">toggle</span>
          </p>
        </div>
      </Command>
    </div>
  );
}
