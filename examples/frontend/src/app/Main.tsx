import React, { ReactNode, useState } from 'react';
import { IndexPage } from './IndexPage';
import { CounterPage } from './examples/counter/CounterPage';

type View = 'index' | 'counter';

interface ExampleMeta {
  title: string;
  render: () => ReactNode;
}

export function Main() {
  const [view, setView] = useState<View>('index');

  const examples: Record<Exclude<View, 'index'>, ExampleMeta> = {
    counter: { title: 'Counter', render: () => <CounterPage /> },
  };

  if (view === 'index') {
    return <IndexPage onSelect={(name) => setView(name)} />;
  }

  const example = examples[view];
  return (
    <div>
      <nav>
        <a
          href="#"
          onClick={(event) => {
            event.preventDefault();
            setView('index');
          }}
        >
          RxDjango Demo
        </a>
        {' -> '}
        <span>{example.title}</span>
      </nav>
      <h1>{example.title}</h1>
      {example.render()}
    </div>
  );
}

export default Main;
