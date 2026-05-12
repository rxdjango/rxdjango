import React, { ReactNode, useEffect, useState } from 'react';
import { RxDjangoLogo } from './RxDjangoLogo';
import { CounterPage } from './examples/counter/CounterPage';
import { CarouselPage } from './examples/carousel/CarouselPage';
import { MemoPage } from './examples/memo/MemoPage';
import { AuthorizationPage } from './examples/authorization/AuthorizationPage';
import { AuthorizationMetaPage } from './examples/authorization_meta/AuthorizationMetaPage';
import { UsageShell } from './UsageShell';

type View = 'index' | 'counter' | 'carousel' | 'memo' | 'authorization' | 'authorization_meta';

/** Extend keys when new @rxdjango/* client snippets ship */
type FrontendSnippetKey = 'react' | 'vue';

interface ExampleMeta {
  title: string;
  description: string;
  codeBackend: string;
  codeFrontend: Record<FrontendSnippetKey, string | undefined>;
  render: () => ReactNode;
}

const sectionHeadingClass =
  'text-xs font-medium uppercase tracking-wide text-primary-700';

const usageHeadingClass =
  `${sectionHeadingClass} border-b border-ink/58 mb-2 p-4`;

function SourceCodeBlock({ code }: { code: string }) {
  const lines = code.split('\n');

  return (
    <div
      className="mt-2 overflow-x-auto rounded-md border border-ink/50 bg-primary-900 font-mono text-xs leading-relaxed"
      role="region"
      aria-label="Source code"
    >
      <div className="flex py-3">
        <div
          aria-hidden="true"
          className="sticky left-0 z-10 shrink-0 select-none border-r border-ink/55 bg-primary-900 py-0 pl-3 pr-4 text-right tabular-nums text-white/70"
        >
          {lines.map((_, index) => (
            <div key={index} className="min-h-[1.375rem]">
              {index + 1}
            </div>
          ))}
        </div>
        <div className="min-w-0 flex-1 pl-5 pr-4">
          {lines.map((line, index) => (
            <div
              key={index}
              className="min-h-[1.375rem] whitespace-pre text-primary-100"
            >
              {line.length === 0 ? '\u00a0' : line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const examples: Record<Exclude<View, 'index'>, ExampleMeta> = {
  counter: {
    title: 'Counter',
    description:
      'A single reactive integer on the channel. Subscribe from React with useChannel, then call increment to run the server-side action and see the value update everywhere it is displayed.',
    codeBackend: [
      '# counter/channels.py',
      '',
      'from rxdjango import ContextChannel, rx, action',
      '',
      'class CounterChannel(ContextChannel):',
      '',
      '    counter = rx[int](0)',
      '',
      '    @action',
      '    async def increment(self):',
      '        self.counter += 1',
    ].join('\n'),
    codeFrontend: {
      react: [
        "import { useChannel } from '@rxdjango/react';",
        "import { CounterChannel } from '../../rx/counter/counter.channels';",
        '',
        'export function CounterDemo() {',
        '  const channel = useChannel(CounterChannel);',
        '',
        '  return (',
        '    <div>',
        '      <p>Value: {channel.counter}</p>',
        '      <button type="button" onClick={channel.increment}>',
        '        Increment',
        '      </button>',
        '    </div>',
        '  );',
        '}',
      ].join('\n'),
      vue: undefined,
    },
    render: () => <CounterPage />,
  },
  carousel: {
    title: 'Carousel',
    description:
      'Three related reactive fields—selected index, fruit name, and first letter—updated together when you call rotate. Shows how the backend can keep a small graph of state consistent in one action.',
    codeBackend: [
      '# carousel/channels.py',
      '',
      'from rxdjango import ContextChannel, rx, action',
      '',
      'class CarouselChannel(ContextChannel):',
      '',
      "    FRUITS = ['banana', 'apple', 'orange']",
      '',
      '    selected = rx[int](0)',
      '    fruit = rx[str](FRUITS[selected])',
      '    first_letter = rx[str](fruit[0])',
      '',
      '    @action',
      '    async def rotate(self):',
      '        self.selected = (self.selected + 1) % len(self.FRUITS)',
      '        self.fruit = self.FRUITS[self.selected]',
      '        self.first_letter = self.fruit[0]',
    ].join('\n'),
    codeFrontend: {
      react: [
        "import { useChannel } from '@rxdjango/react';",
        "import { CarouselChannel } from '../../rx/carousel/carousel.channels';",
        '',
        'export function CarouselDemo() {',
        '  const channel = useChannel(CarouselChannel);',
        '',
        '  return (',
        '    <div>',
        '      <p>Selected: {channel.selected}</p>',
        '      <p>Fruit: {channel.fruit}</p>',
        '      <p>First letter: {channel.first_letter}</p>',
        '      <button type="button" onClick={channel.rotate}>',
        '        Next',
        '      </button>',
        '    </div>',
        '  );',
        '}',
      ].join('\n'),
      vue: undefined,
    },
    render: () => <CarouselPage />,
  },
  memo: {
    title: 'Memo',
    description:
      'Same interaction as Carousel, but fruit and first letter are derived with @memo from selected. Useful when you want stable derived values and explicit dependency tracking on the channel.',
    codeBackend: [
      '# memo/channels.py',
      '',
      'from rxdjango import ContextChannel, rx, action, memo',
      '',
      'class CarouselMemoChannel(ContextChannel):',
      '',
      "    FRUITS = ['banana', 'apple', 'orange']",
      '',
      '    selected = rx[int](0)',
      '',
      '    @action',
      '    async def rotate(self):',
      '        self.selected = (self.selected + 1) % len(self.FRUITS)',
      '',
      "    @memo('selected')",
      '    def fruit(self):',
      '        return self.FRUITS[self.selected]',
      '',
      "    @memo('fruit')",
      '    def first_letter(self):',
      '        return self.fruit[0]',
    ].join('\n'),
    codeFrontend: {
      react: [
        "import { useChannel } from '@rxdjango/react';",
        "import { CarouselMemoChannel } from '../../rx/memo/memo.channels';",
        '',
        'export function MemoDemo() {',
        '  const channel = useChannel(CarouselMemoChannel);',
        '',
        '  return (',
        '    <div>',
        '      <p>Fruit: {channel.fruit}</p>',
        '      <button type="button" onClick={channel.rotate}>',
        '        Next',
        '      </button>',
        '    </div>',
        '  );',
        '}',
      ].join('\n'),
      vue: undefined,
    },
    render: () => <MemoPage />,
  },
  authorization: {
    title: 'Authorization',
    description:
      'increment is declared with requires authorized; authorize checks the password and sets a flag. Until you authorize successfully, the increment action will not run—per-action authorization on the channel.',
    codeBackend: [
      '# authorization/channels.py',
      '',
      'from rxdjango import ContextChannel, rx, action',
      '',
      'class AuthorizationChannel(ContextChannel):',
      '',
      '    authorized: bool = False',
      '    counter = rx[int](0)',
      '',
      '    @action',
      '    async def authorize(self, password: str):',
      "        if password == 'password':",
      '            self.authorized = True',
      '            return True',
      '        return False',
      '',
      "    @action(requires='authorized')",
      '    async def increment(self):',
      '        self.counter += 1',
    ].join('\n'),
    codeFrontend: {
      react: [
        "import { useState } from 'react';",
        "import { useChannel } from '@rxdjango/react';",
        "import { AuthorizationChannel } from '../../rx/authorization/authorization.channels';",
        '',
        'export function AuthorizationDemo() {',
        '  const channel = useChannel(AuthorizationChannel);',
        '  const [password, setPassword] = useState(\'password\');',
        '',
        '  return (',
        '    <div>',
        '      <input',
        '        type="text"',
        '        value={password}',
        '        onChange={(e) => setPassword(e.target.value)}',
        '      />',
        '      <button type="button" onClick={() => channel.authorize(password)}>',
        '        Authorize',
        '      </button>',
        '      <p>Value: {channel.counter}</p>',
        '      <button type="button" onClick={channel.increment}>',
        '        Increment',
        '      </button>',
        '    </div>',
        '  );',
        '}',
      ].join('\n'),
      vue: undefined,
    },
    render: () => <AuthorizationPage />,
  },
  authorization_meta: {
    title: 'Authorization Meta',
    description:
      'Uses Meta.action_requires so every action defaults to requiring authorization, while authorize stays anonymous. Same password flow as Authorization, but the rule is expressed once on the channel class.',
    codeBackend: [
      '# authorization_meta/channels.py',
      '',
      'from rxdjango import ContextChannel, rx, action',
      '',
      'class AuthorizationMetaChannel(ContextChannel):',
      '',
      '    authorized: bool = False',
      '    counter = rx[int](0)',
      '',
      '    class Meta:',
      "        action_requires = 'authorized'",
      '',
      '    @action(anonymous=True)',
      '    async def authorize(self, password: str):',
      "        if password == 'password':",
      '            self.authorized = True',
      '            return True',
      '        return False',
      '',
      '    @action',
      '    async def increment(self):',
      '        self.counter += 1',
    ].join('\n'),
    codeFrontend: {
      react: [
        "import { useState } from 'react';",
        "import { useChannel } from '@rxdjango/react';",
        "import { AuthorizationMetaChannel } from '../../rx/authorization_meta/authorization_meta.channels';",
        '',
        'export function AuthorizationMetaDemo() {',
        '  const channel = useChannel(AuthorizationMetaChannel);',
        '  const [password, setPassword] = useState(\'password\');',
        '',
        '  return (',
        '    <div>',
        '      <input',
        '        type="text"',
        '        value={password}',
        '        onChange={(e) => setPassword(e.target.value)}',
        '      />',
        '      <button type="button" onClick={() => channel.authorize(password)}>',
        '        Authorize',
        '      </button>',
        '      <p>Value: {channel.counter}</p>',
        '      <button type="button" onClick={channel.increment}>',
        '        Increment',
        '      </button>',
        '    </div>',
        '  );',
        '}',
      ].join('\n'),
      vue: undefined,
    },
    render: () => <AuthorizationMetaPage />,
  },
};

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

  const activeExample = view !== 'index' ? examples[view] : null;
  const frontendSnippet =
    activeExample != null ? activeExample.codeFrontend.react : undefined;

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
      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-y-contain bg-primary-100/50">
        <div className="mx-auto w-full max-w-8xl px-6 py-10">
          {view === 'index' ? (
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-ink">
                RxDjango demo
              </h1>
              <p className="mt-4 max-w-prose text-base leading-relaxed text-primary-800">
                A collection of small examples that show how RxDjango keeps a
                React UI in sync with a Django backend through reactive
                channels. Pick an example from the sidebar to see it in action.
              </p>
            </div>
          ) : (
            <div className="flex min-h-0 flex-col">
              <h1 className="text-2xl font-semibold tracking-tight text-ink">
                {examples[view].title}
              </h1>
              <div className="mt-6 grid min-h-0 w-full grid-cols-1 gap-0 divide-y divide-ink/68 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-stretch lg:gap-12 lg:divide-y-0">
                <div
                  className="flex min-h-0 min-w-0 flex-col divide-y divide-ink/68 pb-10 lg:border-r lg:border-ink/68 lg:pb-0 lg:pr-10"
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
                    <SourceCodeBlock code={examples[view].codeBackend} />
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
                    {frontendSnippet != null && frontendSnippet !== '' ? (
                      <SourceCodeBlock code={frontendSnippet} />
                    ) : (
                      <p className="mt-2 text-sm leading-relaxed text-primary-700">
                        Example for this client package is not available yet.
                      </p>
                    )}
                  </section>
                </div>
                <div className="flex min-h-0 min-w-0 w-full flex-col pt-10 lg:pt-0">
                  <div className="flex min-h-0 w-full flex-col rounded-lg bg-white shadow-md lg:sticky lg:top-10 lg:z-10 lg:max-w-full lg:self-start lg:shadow-lg">
                    <div className="flex min-h-0 max-h-[calc(100dvh-7.5rem)] flex-col overflow-y-auto overscroll-y-contain px-1 pt-0 sm:px-0 lg:max-h-[calc(100dvh-9rem)] lg:p-6">
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
        </div>
      </main>
    </div>
  );
}

export default Main;
