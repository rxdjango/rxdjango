import React, { ReactNode, useEffect, useState } from 'react';
import { RxDjangoLogo } from './RxDjangoLogo';
import { CounterPage } from './examples/counter/CounterPage';
import { CarouselPage } from './examples/carousel/CarouselPage';
import { MemoPage } from './examples/memo/MemoPage';
import { AuthorizationPage } from './examples/authorization/AuthorizationPage';
import { AuthorizationMetaPage } from './examples/authorization_meta/AuthorizationMetaPage';
import { UsageShell } from './UsageShell';
import { SourceCodeBlock } from './components/SourceCodeBlock';

type View = 'index' | 'counter' | 'carousel' | 'memo' | 'authorization' | 'authorization_meta';

const API_BASE = '';

interface ExampleMeta {
  title: string;
  description: string;
  backendFile: string;
  frontendFile: string;
  render: () => ReactNode;
}

const sectionHeadingClass =
  'text-xs font-medium uppercase tracking-wide text-primary-700';

const usageHeadingClass =
  `${sectionHeadingClass} border-b border-ink/58 mb-2 p-4`;

const examples: Record<Exclude<View, 'index'>, ExampleMeta> = {
  counter: {
    title: 'Counter',
    description:
      'A single reactive integer on the channel. Subscribe from React with useChannel, then call increment to run the server-side action and see the value update everywhere it is displayed.',
    backendFile: 'channels.py',
    frontendFile: 'CounterPage.tsx',
    render: () => <CounterPage />,
  },
  carousel: {
    title: 'Carousel',
    description:
      'Three related reactive fields—selected index, fruit name, and first letter—updated together when you call rotate. Shows how the backend can keep a small graph of state consistent in one action.',
    backendFile: 'channels.py',
    frontendFile: 'CarouselPage.tsx',
    render: () => <CarouselPage />,
  },
  memo: {
    title: 'Memo',
    description:
      'Same interaction as Carousel, but fruit and first letter are derived with @memo from selected. Useful when you want stable derived values and explicit dependency tracking on the channel.',
    backendFile: 'channels.py',
    frontendFile: 'MemoPage.tsx',
    render: () => <MemoPage />,
  },
  authorization: {
    title: 'Authorization',
    description:
      'increment is declared with requires authorized; authorize checks the password and sets a flag. Until you authorize successfully, the increment action will not run—per-action authorization on the channel.',
    backendFile: 'channels.py',
    frontendFile: 'AuthorizationPage.tsx',
    render: () => <AuthorizationPage />,
  },
  authorization_meta: {
    title: 'Authorization Meta',
    description:
      'Uses Meta.action_requires so every action defaults to requiring authorization, while authorize stays anonymous. Same password flow as Authorization, but the rule is expressed once on the channel class.',
    backendFile: 'channels.py',
    frontendFile: 'AuthorizationMetaPage.tsx',
    render: () => <AuthorizationMetaPage />,
  },
};

function useExampleSource(
  app: Exclude<View, 'index'> | null,
  backendFile: string | null,
  frontendFile: string | null,
) {
  const [backend, setBackend] = useState<string | null>(null);
  const [frontend, setFrontend] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (app == null || backendFile == null || frontendFile == null) {
      setBackend(null);
      setFrontend(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setBackend(null);
    setFrontend(null);
    setError(null);

    const load = async (path: string) => {
      const res = await fetch(`${API_BASE}/src/${app}/${path}`, {
        cache: 'no-store',
      });
      if (!res.ok) {
        throw new Error(`Failed to load ${path}: ${res.status}`);
      }
      return res.text();
    };

    Promise.all([load(backendFile), load(frontendFile)]).then(
      ([backendSrc, frontendSrc]) => {
        if (cancelled) return;
        setBackend(backendSrc);
        setFrontend(frontendSrc);
      },
      (err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      },
    );

    return () => {
      cancelled = true;
    };
  }, [app, backendFile, frontendFile]);

  return { backend, frontend, error };
}

function pathToView(pathname: string): View {
  const segment = pathname.replace(/^\/+|\/+$/g, '');
  if (segment in examples) {
    return segment as View;
  }
  return 'index';
}

function viewToPath(view: View): string {
  return view === 'index' ? '/' : `/${view}`;
}

const navOrder: Exclude<View, 'index'>[] = [
  'counter',
  'carousel',
  'memo',
  'authorization',
  'authorization_meta',
];

function navLinkClass(active: boolean): string {
  const base =
    'block rounded-r-lg border-l-4 py-1.5 pl-3 pr-3 text-sm font-medium text-ink transition-colors';
  if (active) {
    return `${base} border-primary-500 bg-primary-200/50`;
  }
  return `${base} border-transparent hover:border-primary-300 hover:bg-primary-100/80`;
}

export function Main() {
  const [view, setView] = useState<View>(() => pathToView(window.location.pathname));

  useEffect(() => {
    const onPopState = () => {
      setView(pathToView(window.location.pathname));
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const navigate = (next: View) => {
    const path = viewToPath(next);
    if (window.location.pathname !== path) {
      window.history.pushState({}, '', path);
    }
    setView(next);
  };

  const activeApp = view !== 'index' ? view : null;
  const activeExample = activeApp != null ? examples[activeApp] : null;
  const { backend: backendSnippet, frontend: frontendSnippet, error: sourceError } =
    useExampleSource(
      activeApp,
      activeExample?.backendFile ?? null,
      activeExample?.frontendFile ?? null,
    );

  return (
    <div className="flex h-dvh min-h-0 overflow-hidden bg-surface font-sans text-ink">
      <aside className="flex min-h-0 w-60 shrink-0 flex-col overflow-y-auto border-r border-ink/68 bg-surface">
        <div className="border-b border-ink/68 px-4 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => navigate('index')}
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
            href="/"
            className={navLinkClass(view === 'index')}
            onClick={(event) => {
              event.preventDefault();
              navigate('index');
            }}
          >
            Overview
          </a>
          {navOrder.map((key) => {
            const meta = examples[key];
            return (
              <a
                key={key}
                href={viewToPath(key)}
                className={navLinkClass(view === key)}
                onClick={(event) => {
                  event.preventDefault();
                  navigate(key);
                }}
              >
                {meta.title}
              </a>
            );
          })}
        </nav>
      </aside>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-primary-100/50">
        {view === 'index' ? (
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
          <div className="mx-auto flex w-full min-h-0 max-w-8xl flex-1 flex-col px-6 py-10">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">
              {examples[view].title}
            </h1>
            <div className="mt-6 grid min-h-0 w-full flex-1 grid-cols-1 gap-0 divide-y divide-ink/68 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-stretch lg:gap-12 lg:divide-y-0">
              <div
                className="flex min-h-0 min-w-0 flex-col divide-y divide-ink/68 pb-10 lg:overflow-y-auto lg:overscroll-y-contain lg:border-r lg:border-ink/68 lg:pb-0 lg:pr-10"
                aria-label="Documentation"
              >
                  <div className="pb-8">
                    <p className="text-sm leading-relaxed text-primary-800">
                      {examples[view].description}
                    </p>
                  </div>
                  <section
                    aria-labelledby={`${view}-backend`}
                    className="space-y-2 py-8"
                  >
                    <h2 id={`${view}-backend`} className={sectionHeadingClass}>
                      Backend (Django)
                    </h2>
                    {sourceError != null ? (
                      <p className="mt-2 text-sm leading-relaxed text-primary-700">
                        Failed to load source: {sourceError}
                      </p>
                    ) : backendSnippet != null ? (
                      <SourceCodeBlock code={backendSnippet} language="python" />
                    ) : (
                      <p className="mt-2 text-sm leading-relaxed text-primary-700">
                        Loading…
                      </p>
                    )}
                  </section>
                  <section
                    aria-labelledby={`${view}-frontend`}
                    className="space-y-2 pt-8"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                      <h2 id={`${view}-frontend`} className={sectionHeadingClass}>
                        Frontend
                      </h2>
                      <div
                        className="inline-flex shrink-0 rounded-md border border-ink/42 bg-surface p-0.5"
                        aria-label="Client package: React"
                      >
                        <span className="min-w-[5.5rem] rounded px-2.5 py-1.5 text-left text-xs font-medium bg-primary-500 text-white">
                          <span className="block leading-tight">React</span>
                          <span className="mt-0.5 block text-[10px] font-normal leading-tight opacity-90">
                            @rxdjango/react
                          </span>
                        </span>
                      </div>
                    </div>
                    {sourceError != null ? (
                      <p className="mt-2 text-sm leading-relaxed text-primary-700">
                        Failed to load source: {sourceError}
                      </p>
                    ) : frontendSnippet != null ? (
                      <SourceCodeBlock code={frontendSnippet} language="typescript" />
                    ) : (
                      <p className="mt-2 text-sm leading-relaxed text-primary-700">
                        Loading…
                      </p>
                    )}
                  </section>
                </div>
                <div className="flex min-h-0 min-w-0 w-full flex-col pt-10 lg:pt-0">
                  <div className="flex min-h-0 w-full flex-1 flex-col rounded-lg bg-white shadow-md lg:z-10 lg:max-w-full lg:self-stretch lg:shadow-lg">
                    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-y-contain px-1 pt-0 sm:px-0 lg:p-6">
                      <section aria-labelledby={`${view}-usage`}>
                        <h2 id={`${view}-usage`} className={usageHeadingClass}>
                          Usage
                        </h2>
                        <UsageShell>
                          {examples[view].render()}
                        </UsageShell>
                      </section>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
      </main>
    </div>
  );
}

export default Main;
