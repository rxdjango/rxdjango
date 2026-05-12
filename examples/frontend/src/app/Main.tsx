import React, { useEffect, useState } from 'react';
import { RxDjangoLogo } from './RxDjangoLogo';
import { pages, type Page } from './examples/pages.generated';

// CRA sets PUBLIC_URL from package.json "homepage" at build time;
// it is "" in dev and e.g. "/react" in production.
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

function pageForPath(pathname: string): Page | null {
  const segment = stripBasename(pathname).replace(/^\/+|\/+$/g, '');
  return pages.find(([app]) => app === segment) ?? null;
}

function navLinkClass(active: boolean): string {
  const base =
    'block rounded-r-lg border-l-4 py-1.5 pl-3 pr-3 text-sm font-medium text-ink transition-colors';
  if (active) {
    return `${base} border-primary-500 bg-primary-200/50`;
  }
  return `${base} border-transparent hover:border-primary-300 hover:bg-primary-100/80`;
}

export function Main() {
  const [active, setActive] = useState<Page | null>(() =>
    pageForPath(window.location.pathname),
  );

  useEffect(() => {
    const onPopState = () => {
      setActive(pageForPath(window.location.pathname));
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const navigate = (page: Page | null) => {
    const path = withBasename(page == null ? '/' : `/${page[0]}`);

    if (window.location.pathname !== path) {
      window.history.pushState({}, '', path);
    }
    setActive(page);
  };

  const activeApp = active?.[0] ?? null;
  const ActiveComponent = active?.[2] ?? null;

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
            <p className="shrink-0 text-xs font-medium uppercase tracking-wide text-primary-700">
              Examples
            </p>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-0 p-2" aria-label="Examples">
          <a
            href={withBasename('/')}
            className={navLinkClass(active == null)}
            onClick={(event) => {
              event.preventDefault();
              navigate(null);
            }}
          >
            Overview
          </a>
          {pages.map((page) => {
            const [app, title] = page;
            return (
              <a
                key={app}
                href={withBasename(`/${app}`)}
                className={navLinkClass(activeApp === app)}
                onClick={(event) => {
                  event.preventDefault();
                  navigate(page);
                }}
              >
                {title}
              </a>
            );
          })}
        </nav>
      </aside>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-primary-100/50">
        {ActiveComponent == null ? (
          <div className="flex-1 overflow-y-auto overscroll-y-contain">
            <div className="mx-auto w-full max-w-8xl px-6 py-10">
              <h1 className="text-2xl font-semibold tracking-tight text-ink">
                RxDjango demo
              </h1>
              <p className="mt-4 max-w-prose text-base leading-relaxed text-primary-800">
                A collection of small examples that show how RxDjango keeps a
                React UI in sync with a Django backend through reactive
                channels. Pick an example from the sidebar to see it in action.
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
