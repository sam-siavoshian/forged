import { NavLink, useNavigate } from 'react-router-dom';
import { XIcon } from 'lucide-animated';
import { DOCS_NAV } from '../../docs/constants';

interface DocsSidebarProps {
  mobileOpen: boolean;
  onMobileClose: () => void;
}

export function DocsSidebar({ mobileOpen, onMobileClose }: DocsSidebarProps) {
  const navigate = useNavigate();

  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
          aria-hidden
          onClick={onMobileClose}
        />
      )}

      <aside
        className={`
          fixed md:relative z-50 h-screen md:h-full md:min-h-0 flex flex-col
          bg-sidebar border-r border-sidebar-border
          will-change-transform
          w-[220px] shrink-0
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
        style={{
          transition: 'transform 200ms cubic-bezier(0.25, 0.1, 0.25, 1)',
        }}
      >
        <div className="flex items-center h-14 px-3 border-b border-sidebar-border gap-2">
          <div className="min-w-0 flex-1 pl-1">
            <span className="text-[13px] font-semibold text-text tracking-tight block truncate">
              Documentation
            </span>
          </div>
          <button
            type="button"
            onClick={onMobileClose}
            className="md:hidden ml-auto w-7 h-7 flex items-center justify-center rounded-lg text-text-muted hover:text-text shrink-0"
            aria-label="Close menu"
          >
            <XIcon size={14} />
          </button>
        </div>

        <nav className="flex-1 flex flex-col gap-0.5 py-3 px-3 min-h-0 overflow-y-auto">
          <p className="text-[10px] font-mono uppercase tracking-[0.12em] text-text-muted px-3 py-1.5">
            Reference
          </p>

          {DOCS_NAV.map(({ path, label }) => (
            <NavLink
              key={path}
              to={path}
              onClick={onMobileClose}
              className={({ isActive }) =>
                `sidebar-nav-item ${isActive ? 'active' : ''}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-sidebar-border py-3 px-3">
          <button
            type="button"
            onClick={() => {
              navigate('/');
              onMobileClose();
            }}
            className="sidebar-nav-item w-full text-left"
          >
            Back to app
          </button>
          <p className="text-[10px] font-mono text-text-muted/80 px-3 pt-3">⌘K search</p>
        </div>
      </aside>
    </>
  );
}
