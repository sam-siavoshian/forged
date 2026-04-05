import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  RocketIcon,
  HomeIcon,
  BrainIcon,
  ZapIcon,
  LayersIcon,
  MenuIcon,
  XIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  FileTextIcon,
} from 'lucide-animated';
import type { Template } from '../types';

interface AppSidebarProps {
  templates: Template[];
  sidebarOpen: boolean;
  onToggle: () => void;
  collapsed: boolean;
  onCollapse: (collapsed: boolean) => void;
}

const RL_NAV_ITEMS = [
  { path: '/rl/learn', label: 'Learn', icon: BrainIcon },
  { path: '/rl/race', label: 'Race', icon: ZapIcon },
] as const;

export function AppSidebar({ templates, sidebarOpen, onToggle, collapsed, onCollapse }: AppSidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname.replace(/\/+$/, '') || '/';
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed md:relative z-50 h-screen flex flex-col
          bg-sidebar border-r border-sidebar-border
          will-change-transform
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          ${collapsed ? 'w-[60px]' : 'w-[220px]'}
        `}
        style={{
          transition: 'transform 200ms cubic-bezier(0.25, 0.1, 0.25, 1), width 200ms cubic-bezier(0.25, 0.1, 0.25, 1)',
        }}
      >
        {/* Header */}
        <div className={`flex items-center h-14 px-3 border-b border-sidebar-border ${collapsed ? 'justify-center' : 'justify-between'}`}>
          {!collapsed && (
            <div className="flex items-center gap-2.5 pl-1">
              <div className="w-7 h-7 rounded-lg bg-lime/10 flex items-center justify-center">
                <RocketIcon size={14} className="text-lime" />
              </div>
              <span className="text-[14px] font-semibold text-text tracking-tight">Rocket</span>
            </div>
          )}
          {collapsed && (
            <div className="w-7 h-7 rounded-lg bg-lime/10 flex items-center justify-center">
              <RocketIcon size={14} className="text-lime" />
            </div>
          )}
          <button
            onClick={() => onCollapse(!collapsed)}
            className="hidden md:flex w-7 h-7 items-center justify-center rounded-lg text-text-muted hover:text-text hover:bg-white/5 transition-all"
          >
            <ChevronLeftIcon size={14} className={`transition-transform duration-300 ${collapsed ? 'rotate-180' : ''}`} />
          </button>
          <button
            onClick={onToggle}
            className="md:hidden w-7 h-7 flex items-center justify-center rounded-lg text-text-muted hover:text-text"
          >
            <XIcon size={14} />
          </button>
        </div>

        {/* Navigation */}
        <nav className={`flex-1 flex flex-col gap-1 py-3 ${collapsed ? 'px-2' : 'px-3'}`}>
          {/* New Chat button */}
          <button
            onClick={() => { navigate('/'); if (sidebarOpen) onToggle(); }}
            className={`sidebar-nav-item ${collapsed ? 'justify-center px-0' : ''} ${
              currentPath === '/' ? 'active' : ''
            }`}
            title={collapsed ? 'New Chat' : undefined}
          >
            <HomeIcon size={16} className={currentPath === '/' ? 'text-lime' : ''} />
            {!collapsed && <span>New Chat</span>}
          </button>

          {/* Divider */}
          <div className={`h-px bg-sidebar-border my-2 ${collapsed ? 'mx-1' : 'mx-1'}`} />

          {/* RL Training section */}
          {!collapsed && (
            <p className="text-[10px] font-mono uppercase tracking-[0.12em] text-text-muted px-3 py-1">
              RL Training
            </p>
          )}
          {RL_NAV_ITEMS.map(({ path, label, icon: Icon }) => {
            const active = currentPath === path || currentPath === path.replace('/rl', '');
            return (
              <button
                key={path}
                onClick={() => { navigate(path); if (sidebarOpen) onToggle(); }}
                className={`sidebar-nav-item ${active ? 'active' : ''} ${collapsed ? 'justify-center px-0' : ''}`}
                title={collapsed ? label : undefined}
              >
                <Icon size={16} className={active ? 'text-lime' : ''} />
                {!collapsed && <span>{label}</span>}
              </button>
            );
          })}

          {/* Divider */}
          <div className={`h-px bg-sidebar-border my-2 ${collapsed ? 'mx-1' : 'mx-1'}`} />

          {/* Templates section */}
          {!collapsed && (
            <div className="flex flex-col gap-0.5">
              <p className="text-[10px] font-mono uppercase tracking-[0.12em] text-text-muted px-3 py-1.5">
                Learned
              </p>
              {templates.length === 0 ? (
                <p className="text-[11px] text-text-muted/60 px-3 py-1">No templates yet</p>
              ) : (
                <div className="flex flex-col gap-0.5 max-h-[320px] overflow-y-auto">
                  {templates.slice(0, 10).map((t) => {
                    const isExpanded = expandedId === t.id;
                    const stepTypeColor = (type: string) =>
                      type === 'fixed' ? 'bg-lime' :
                      type === 'parameterized' ? 'bg-amber' :
                      'bg-sky';
                    return (
                      <div key={t.id} className="flex flex-col">
                        <button
                          type="button"
                          onClick={() => setExpandedId(isExpanded ? null : t.id)}
                          className="flex items-center gap-2 px-3 py-2 rounded-xl text-[11px] text-text-dim hover:bg-white/[0.04] transition-all cursor-pointer group/tmpl w-full text-left"
                          style={{
                            boxShadow: isExpanded
                              ? 'inset 0 3px 8px rgba(0,0,0,0.2), inset 0 -1px 3px rgba(255,255,255,0.02)'
                              : 'none',
                            background: isExpanded ? 'rgba(255,255,255,0.03)' : undefined,
                          }}
                        >
                          <DomainFavicon domain={t.domain} />
                          <span className="truncate flex-1">{t.domain}</span>
                          <ChevronRightIcon
                            size={12}
                            className={`shrink-0 text-text-muted/50 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
                          />
                        </button>

                        {/* Expanded step list */}
                        {isExpanded && t.steps && t.steps.length > 0 && (
                          <div
                            className="mx-2 mb-1 mt-0.5 rounded-xl overflow-hidden"
                            style={{
                              background: 'rgba(0,0,0,0.2)',
                              boxShadow: 'inset 0 4px 10px rgba(0,0,0,0.4), inset 0 1px 3px rgba(0,0,0,0.25), inset 0 -1px 3px rgba(255,255,255,0.015)',
                            }}
                          >
                            {t.steps.map((step, i) => (
                              <div
                                key={step.id}
                                className="flex items-start gap-2 px-2.5 py-1.5 text-[10px] leading-tight"
                                style={{
                                  borderTop: i > 0 ? '1px solid rgba(255,255,255,0.025)' : undefined,
                                }}
                              >
                                <div className={`w-[3px] h-3 rounded-full shrink-0 mt-0.5 ${stepTypeColor(step.type)}`}
                                  style={{ opacity: step.type === 'fixed' ? 0.7 : 0.4 }}
                                />
                                <span className="text-text-muted leading-snug flex-1">
                                  {step.description}
                                </span>
                                {step.handoff && (
                                  <span className="text-[8px] font-mono text-sky/60 shrink-0 mt-0.5">handoff</span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                        {isExpanded && (!t.steps || t.steps.length === 0) && (
                          <p className="text-[10px] text-text-muted/40 px-5 py-1.5">No steps recorded</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {collapsed && templates.length > 0 && (
            <button
              className="sidebar-nav-item justify-center px-0"
              title={`${templates.length} learned templates`}
            >
              <LayersIcon size={16} />
            </button>
          )}
        </nav>

        {/* Footer */}
        <div className={`border-t border-sidebar-border py-3 flex flex-col gap-2 ${collapsed ? 'px-2' : 'px-3'}`}>
          <button
            type="button"
            onClick={() => { navigate('/docs/overview'); if (sidebarOpen) onToggle(); }}
            className={`sidebar-nav-item w-full ${collapsed ? 'justify-center px-0' : ''} ${
              currentPath.startsWith('/docs') ? 'active' : ''
            }`}
            title={collapsed ? 'API docs' : undefined}
          >
            <FileTextIcon size={16} className={currentPath.startsWith('/docs') ? 'text-lime' : ''} />
            {!collapsed && <span>API docs</span>}
          </button>
        </div>
      </aside>
    </>
  );
}

function DomainFavicon({ domain }: { domain: string }) {
  const [failed, setFailed] = useState(false);
  const cleanDomain = domain.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
  const faviconUrl = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(cleanDomain)}&sz=32`;

  if (failed) {
    return <LayersIcon size={12} className="text-text-muted shrink-0" />;
  }

  return (
    <img
      src={faviconUrl}
      alt=""
      width={14}
      height={14}
      className="shrink-0 rounded-sm"
      onError={() => setFailed(true)}
      loading="lazy"
    />
  );
}

export function MobileTopBar({ onToggle }: { onToggle: () => void }) {
  return (
    <div className="md:hidden flex items-center h-12 px-4 border-b border-sidebar-border bg-sidebar">
      <button
        onClick={onToggle}
        className="w-8 h-8 flex items-center justify-center rounded-lg text-text-dim hover:text-text hover:bg-white/5 transition-all"
      >
        <MenuIcon size={16} />
      </button>
      <div className="flex items-center gap-2 ml-3">
        <div className="w-6 h-6 rounded-md bg-lime/10 flex items-center justify-center">
          <RocketIcon size={12} className="text-lime" />
        </div>
        <span className="text-[13px] font-semibold text-text">Rocket</span>
      </div>
    </div>
  );
}
