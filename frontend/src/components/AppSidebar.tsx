import { useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  FlameIcon,
  MessageCircleIcon,
  BrainIcon,
  ZapIcon,
  GaugeIcon,
  LayersIcon,
  MenuIcon,
  XIcon,
  ChevronLeftIcon,
  FileTextIcon,
  type BrainIconHandle,
  type ZapIconHandle,
  type FileTextIconHandle,
  type LayersIconHandle,
  type GaugeIconHandle,
} from 'lucide-animated';
import type { Template } from '../types';

interface AppSidebarProps {
  templates: Template[];
  sidebarOpen: boolean;
  onToggle: () => void;
  collapsed: boolean;
  onCollapse: (collapsed: boolean) => void;
}

export function AppSidebar({ templates, sidebarOpen, onToggle, collapsed, onCollapse }: AppSidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname.replace(/\/+$/, '') || '/';
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const brainIconRef = useRef<BrainIconHandle>(null);
  const zapIconRef = useRef<ZapIconHandle>(null);
  const gaugeIconRef = useRef<GaugeIconHandle>(null);
  const fileTextIconRef = useRef<FileTextIconHandle>(null);
  const layersIconRef = useRef<LayersIconHandle>(null);

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
          fixed md:relative z-50 h-full min-h-0 flex flex-col
          inset-y-0 md:inset-y-auto
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
          <button
            type="button"
            onClick={() => navigate('/learn')}
            className={`flex items-center gap-2.5 pl-1 rounded-lg hover:bg-white/[0.04] transition-colors cursor-pointer ${collapsed ? 'justify-center p-0' : ''}`}
            title="Chat"
          >
            <div className="w-7 h-7 rounded-lg bg-lime/10 flex items-center justify-center shrink-0">
              <FlameIcon size={14} className="text-lime" />
            </div>
            {!collapsed && (
              <span className="text-[14px] font-semibold text-text tracking-tight">Forge</span>
            )}
          </button>
          <button
            type="button"
            onClick={() => onCollapse(!collapsed)}
            className="hidden md:flex w-7 h-7 items-center justify-center rounded-lg text-text-muted hover:text-text hover:bg-white/5 transition-all cursor-pointer"
          >
            <ChevronLeftIcon size={14} className={`transition-transform duration-300 ${collapsed ? 'rotate-180' : ''}`} />
          </button>
          <button
            type="button"
            onClick={onToggle}
            className="md:hidden w-7 h-7 flex items-center justify-center rounded-lg text-text-muted hover:text-text cursor-pointer"
          >
            <XIcon size={14} />
          </button>
        </div>

        {/* Navigation */}
        <nav className={`flex-1 flex flex-col gap-1 py-3 ${collapsed ? 'px-2' : 'px-3'}`}>
          {/* Browser chat — /learn (default app entry) */}
          <button
            type="button"
            onClick={() => { navigate('/learn'); if (sidebarOpen) onToggle(); }}
            className={`sidebar-nav-item ${collapsed ? 'justify-center px-0' : ''} ${
              currentPath === '/learn' ||
              currentPath.startsWith('/learn/') ||
              currentPath.startsWith('/chat/')
                ? 'active'
                : ''
            }`}
            title={collapsed ? 'Chat' : undefined}
          >
            <MessageCircleIcon
              size={16}
              className={
                currentPath === '/learn' ||
                currentPath.startsWith('/learn/') ||
                currentPath.startsWith('/chat/')
                  ? 'text-lime'
                  : ''
              }
            />
            {!collapsed && <span>Chat</span>}
          </button>

          {/* Divider */}
          <div className={`h-px bg-sidebar-border my-2 ${collapsed ? 'mx-1' : 'mx-1'}`} />

          {/* RL Training section */}
          {!collapsed && (
            <p className="text-[10px] font-mono uppercase tracking-[0.12em] text-text-muted px-3 py-1">
              RL Training
            </p>
          )}
          {(() => {
            const learnPath = '/rl/learn';
            // Only /rl/learn — do not use "/learn" here (that is the browser chat route).
            const learnActive = currentPath === learnPath;
            const racePath = '/rl/race';
            const raceActive = currentPath === racePath || currentPath === '/race';
            return (
              <>
                <button
                  type="button"
                  onClick={() => {
                    navigate(learnPath);
                    if (sidebarOpen) onToggle();
                  }}
                  onMouseEnter={() => brainIconRef.current?.startAnimation()}
                  onMouseLeave={() => brainIconRef.current?.stopAnimation()}
                  className={`sidebar-nav-item ${learnActive ? 'active' : ''} ${collapsed ? 'justify-center px-0' : ''}`}
                  title={collapsed ? 'Learn' : undefined}
                >
                  <BrainIcon
                    ref={brainIconRef}
                    size={16}
                    className={learnActive ? 'text-lime' : ''}
                  />
                  {!collapsed && <span>Learn</span>}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    navigate(racePath);
                    if (sidebarOpen) onToggle();
                  }}
                  onMouseEnter={() => zapIconRef.current?.startAnimation()}
                  onMouseLeave={() => zapIconRef.current?.stopAnimation()}
                  className={`sidebar-nav-item ${raceActive ? 'active' : ''} ${collapsed ? 'justify-center px-0' : ''}`}
                  title={collapsed ? 'Race' : undefined}
                >
                  <ZapIcon ref={zapIconRef} size={16} className={raceActive ? 'text-lime' : ''} />
                  {!collapsed && <span>Race</span>}
                </button>
              </>
            );
          })()}
          {(() => {
            const benchActive = currentPath === '/benchmarks';
            return (
              <button
                type="button"
                onClick={() => {
                  navigate('/benchmarks');
                  if (sidebarOpen) onToggle();
                }}
                onMouseEnter={() => gaugeIconRef.current?.startAnimation()}
                onMouseLeave={() => gaugeIconRef.current?.stopAnimation()}
                className={`sidebar-nav-item ${benchActive ? 'active' : ''} ${collapsed ? 'justify-center px-0' : ''}`}
                title={collapsed ? 'Benchmarks' : undefined}
              >
                <GaugeIcon ref={gaugeIconRef} size={16} className={benchActive ? 'text-lime' : ''} />
                {!collapsed && <span>Benchmarks</span>}
              </button>
            );
          })()}

          {/* Divider */}
          <div className={`h-px bg-sidebar-border my-2 ${collapsed ? 'mx-1' : 'mx-1'}`} />

          {/* Templates section */}
          {!collapsed && (
            <div className="flex flex-col gap-0.5">
              <div className="flex items-center gap-2 px-3 py-1.5">
                <p className="text-[10px] font-mono uppercase tracking-[0.12em] text-text-muted">
                  Learned
                </p>
                {templates.length > 0 && (
                  <span className="text-[9px] font-mono font-bold bg-lime/15 text-lime px-1.5 py-[1px] rounded-full">
                    {templates.length}
                  </span>
                )}
              </div>
              {templates.length === 0 ? (
                <p className="text-[11px] text-text-muted/60 px-3 py-1">No learnings yet</p>
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
                          <ChevronLeftIcon
                            size={12}
                            className={`shrink-0 text-text-muted/50 transition-transform duration-200 ${isExpanded ? 'rotate-90' : 'rotate-180'}`}
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
              type="button"
              className="sidebar-nav-item justify-center px-0"
              title={`${templates.length} saved learnings`}
              onMouseEnter={() => layersIconRef.current?.startAnimation()}
              onMouseLeave={() => layersIconRef.current?.stopAnimation()}
            >
              <LayersIcon ref={layersIconRef} size={16} />
            </button>
          )}
        </nav>

        {/* Footer */}
        <div className={`border-t border-sidebar-border py-3 flex flex-col gap-2 ${collapsed ? 'px-2' : 'px-3'}`}>
          <button
            type="button"
            onClick={() => { navigate('/docs/overview'); if (sidebarOpen) onToggle(); }}
            onMouseEnter={() => fileTextIconRef.current?.startAnimation()}
            onMouseLeave={() => fileTextIconRef.current?.stopAnimation()}
            className={`sidebar-nav-item w-full ${collapsed ? 'justify-center px-0' : ''} ${
              currentPath.startsWith('/docs') ? 'active' : ''
            }`}
            title={collapsed ? 'API docs' : undefined}
          >
            <FileTextIcon
              ref={fileTextIconRef}
              size={16}
              className={currentPath.startsWith('/docs') ? 'text-lime' : ''}
            />
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
          <FlameIcon size={12} className="text-lime" />
        </div>
        <span className="text-[13px] font-semibold text-text">Forge</span>
      </div>
    </div>
  );
}
