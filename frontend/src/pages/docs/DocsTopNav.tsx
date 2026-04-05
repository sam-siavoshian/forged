import { MenuIcon, SearchIcon } from 'lucide-animated';

interface DocsTopNavProps {
  onOpenSearch: () => void;
  onOpenMenu: () => void;
}

/** Linear-style top bar: slim, hairline border, compact ⌘K search trigger */
export function DocsTopNav({ onOpenSearch, onOpenMenu }: DocsTopNavProps) {
  return (
    <header className="flex items-center gap-2 h-12 px-3 md:px-4 border-b border-border/80 bg-bg/95 backdrop-blur-md shrink-0 relative z-30">
      <div className="flex shrink-0 md:w-0">
        <button
          type="button"
          onClick={onOpenMenu}
          className="md:hidden w-9 h-9 flex items-center justify-center rounded-md text-text-muted hover:text-text hover:bg-white/[0.05] transition-colors duration-100"
          aria-label="Open documentation menu"
        >
          <MenuIcon size={17} />
        </button>
      </div>

      <div className="flex-1 flex justify-center min-w-0 px-0.5 md:px-3">
        <button
          type="button"
          onClick={onOpenSearch}
          className="group w-full max-w-md flex items-center gap-2.5 h-9 px-3 rounded-md border border-border/90 bg-elevated hover:bg-white/[0.03] hover:border-border transition-colors duration-100 text-left"
          aria-label="Search documentation"
        >
          <SearchIcon size={15} className="text-text-muted shrink-0 opacity-80" />
          <span className="flex-1 text-[13px] text-text-muted truncate select-none">
            Search documentation…
          </span>
          <kbd className="hidden sm:inline-flex items-center shrink-0 px-1.5 py-0.5 rounded border border-border/70 bg-black/40 font-mono text-[10px] text-text-muted tabular-nums">
            ⌘K
          </kbd>
        </button>
      </div>

      <div className="shrink-0 w-9 md:w-10" aria-hidden />
    </header>
  );
}
