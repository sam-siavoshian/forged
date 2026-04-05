import { useMemo, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { VALID_DOC_SLUGS } from '../../docs/constants';
import { DocsSidebar } from './DocsSidebar';
import { DocsTopNav } from './DocsTopNav';
import { DocsCommandPalette } from '../../components/docs/DocsCommandPalette';
import { OverviewPage } from './pages/OverviewPage';
import { IntegrationPage } from './pages/IntegrationPage';
import { EndpointsPage } from './pages/EndpointsPage';
import { ModelsPage } from './pages/ModelsPage';
import { EnvironmentPage } from './pages/EnvironmentPage';

function docSlugFromPath(pathname: string): string | null {
  const p = pathname.replace(/\/+$/, '') || '/';
  if (p === '/docs') return null;
  if (!p.startsWith('/docs/')) return 'overview';
  const slug = p.slice('/docs/'.length);
  if (!slug || slug.includes('/')) return 'invalid';
  return slug;
}

export function DocsLayout() {
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  const slug = useMemo(() => docSlugFromPath(location.pathname), [location.pathname]);

  if (slug === null) {
    return <Navigate to="/docs/overview" replace />;
  }

  if (slug === 'invalid' || !VALID_DOC_SLUGS.has(slug)) {
    return <Navigate to="/docs/overview" replace />;
  }

  const page = (
    <div key={slug} className="anim-fade-up">
      {slug === 'overview' && <OverviewPage />}
      {slug === 'integration' && <IntegrationPage />}
      {slug === 'endpoints' && <EndpointsPage />}
      {slug === 'models' && <ModelsPage />}
      {slug === 'environment' && <EnvironmentPage />}
    </div>
  );

  return (
    <div className="flex flex-col flex-1 min-h-0 w-full min-w-0 relative z-10">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `radial-gradient(ellipse 90% 55% at 100% -10%, rgba(200,255,0,0.12) 0%, transparent 52%),
            radial-gradient(ellipse 70% 45% at 0% 100%, rgba(56,189,248,0.06) 0%, transparent 48%)`,
        }}
        aria-hidden
      />

      <DocsTopNav onOpenSearch={() => setSearchOpen(true)} onOpenMenu={() => setMobileNavOpen(true)} />

      <div className="flex flex-1 min-h-0 min-w-0 relative">
        <DocsSidebar mobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />

        <main className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden scroll-smooth">
          <div className="max-w-2xl mx-auto px-5 md:px-8 pt-7 md:pt-10 pb-20 md:pb-24">{page}</div>
        </main>
      </div>

      <DocsCommandPalette open={searchOpen} onOpenChange={setSearchOpen} />
    </div>
  );
}
