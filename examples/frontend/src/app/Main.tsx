import React, { useEffect, useState } from 'react';
import { RxDjangoLogo } from './RxDjangoLogo';
import { pages, type Page } from './pages.generated';

const BASENAME = (process.env.PUBLIC_URL || '').replace(/\/+$/, '');

function stripBasename(pathname: string): string {
  if (BASENAME && pathname.startsWith(BASENAME)) {
    return pathname.slice(BASENAME.length) || '/';
  }
  return pathname;
}

function withBasename(path: string): string {
  return `${BASENAME}${path}`;
}

function routeForPath(pathname: string): { page: Page | null; demoOnly: boolean } {
  const stripped = stripBasename(pathname).replace(/^\/+|\/+$/g, '');
  if (stripped === '') {
    return { page: null, demoOnly: false };
  }
  const segments = stripped.split('/');
  const last = segments[segments.length - 1];
  const demoOnly = last === 'demo';
  const slug = demoOnly ? segments.slice(0, -1).join('/') : stripped;
  const page = pages.find((p) => p.slug === slug) ?? null;
  return { page, demoOnly: demoOnly && page != null };
}

function ancestorsOf(slug: string | null): Set<string> {
  const result = new Set<string>();
  if (!slug) {
    return result;
  }
  const parts = slug.split('/');
  for (let i = 1; i <= parts.length; i++) {
    result.add(parts.slice(0, i).join('/'));
  }
  return result;
}

function navLinkClass(active: boolean, ancestor: boolean): string {
  const base =
    'block rounded-r-lg border-l-4 py-1.5 pl-3 pr-3 text-sm font-medium text-ink transition-colors';
  if (active) {
    return `${base} border-primary-500 bg-primary-200/50`;
  }
  if (ancestor) {
    return `${base} border-primary-400 bg-primary-100/60`;
  }
  return `${base} border-transparent hover:border-primary-300 hover:bg-primary-100/80`;
}

export function Main() {
  const [route, setRoute] = useState<{ page: Page | null; demoOnly: boolean }>(
    () => routeForPath(window.location.pathname),
  );

  useEffect(() => {
    const onPopState = () => {
      setRoute(routeForPath(window.location.pathname));
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const navigate = (page: Page | null) => {
    const path = withBasename(page == null ? '/' : `/${page.slug}`);
    if (window.location.pathname !== path) {
      window.history.pushState({}, '', path);
    }
    setRoute({ page, demoOnly: false });
  };

  const active = route.page;
  const ActiveComponent = active?.Component ?? null;
  const ActiveDemo = active?.Demo ?? null;
  const activeSlugs = ancestorsOf(active?.slug ?? null);

  if (route.demoOnly && ActiveDemo != null) {
    return (
      <div className="min-h-dvh bg-transparent p-6 font-sans text-ink">
        <ActiveDemo />
      </div>
    );
  }

  return (
    <div className="flex h-dvh min-h-0 overflow-hidden bg-surface font-sans text-ink">
      <aside className="flex min-h-0 w-60 shrink-0 flex-col overflow-y-auto border-r border-ink/68 bg-surface">
        <div className="border-b border-ink/68 px-4 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => navigate(null)}
              className="min-w-0 flex-1 text-left transition-opacity hover:opacity-90"
            >
              <RxDjangoLogo className="h-8 w-auto max-w-full" />
            </button>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-0 p-2" aria-label="Documentation">
          <a
            href={withBasename('/')}
            className={navLinkClass(active == null, false)}
            onClick={(event) => {
              event.preventDefault();
              navigate(null);
            }}
          >
            Home
          </a>
          {pages.map((page) => {
            const isActive = active?.slug === page.slug;
            const isAncestor = !isActive && activeSlugs.has(page.slug);
            return (
              <a
                key={page.slug}
                href={withBasename(`/${page.slug}`)}
                className={navLinkClass(isActive, isAncestor)}
                style={{ paddingLeft: `${0.75 + page.depth * 1}rem` }}
                onClick={(event) => {
                  event.preventDefault();
                  navigate(page);
                }}
              >
                {page.title}
              </a>
            );
          })}
        </nav>
      </aside>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-primary-100/50">
        {ActiveComponent == null ? (
          <div className="flex-1 overflow-y-auto overscroll-y-contain">
            <div className="mx-auto w-full max-w-3xl px-6 py-10">
              <h1 className="text-2xl font-semibold tracking-tight text-ink">
                RxDjango
              </h1>
              <p className="mt-4 max-w-prose text-base leading-relaxed text-primary-800">
                A reactive layer for Django that keeps a TypeScript UI in
                sync with the server through typed channels. Pick a page
                from the sidebar to start.
              </p>
            </div>
          </div>
        ) : (
          <ActiveComponent />
        )}
      </main>
    </div>
  );
}

export default Main;
