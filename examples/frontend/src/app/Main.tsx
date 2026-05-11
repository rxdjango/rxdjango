import React, { ReactNode, useEffect, useState } from 'react';
import { IndexPage } from './IndexPage';
import { CounterPage } from './examples/counter/CounterPage';
import { CarouselPage } from './examples/carousel/CarouselPage';
import { MemoPage } from './examples/memo/MemoPage';

type View = 'index' | 'counter' | 'carousel' | 'memo';

interface ExampleMeta {
  title: string;
  render: () => ReactNode;
}

const examples: Record<Exclude<View, 'index'>, ExampleMeta> = {
  counter: { title: 'Counter', render: () => <CounterPage /> },
  carousel: { title: 'Carousel', render: () => <CarouselPage /> },
  memo: { title: 'Memo', render: () => <MemoPage /> },
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

  if (view === 'index') {
    return <IndexPage onSelect={(name) => navigate(name)} />;
  }

  const example = examples[view];
  return (
    <div>
      <nav>
        <a
          href="/"
          onClick={(event) => {
            event.preventDefault();
            navigate('index');
          }}
        >
          RxDjango Demo
        </a>
        {' -> '}
        <span>
          {example.title}
        </span>
      </nav>
      <h1>
        {example.title}
      </h1>
      {example.render()}
    </div>
  );
}

export default Main;
