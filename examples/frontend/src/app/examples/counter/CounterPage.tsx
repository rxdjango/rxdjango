import React from 'react';
import { useChannel } from '@rxdjango/react';
import { CounterChannel } from '../../rx/counter/counter.channels';

interface CounterPageProps {
  onBack: () => void;
}

export function CounterPage({ onBack }: CounterPageProps) {
  const channel = useChannel(CounterChannel);

  return (
    <div>
      <nav>
        <a
          href="#"
          onClick={(event) => {
            event.preventDefault();
            onBack();
          }}
        >
          RxDjango Demo
        </a>
        {' -> '}
        <span>Counter</span>
      </nav>
      <h1>Counter</h1>
      <p>Value: {channel.counter}</p>
      <button onClick={() => channel.increment()}>Increment</button>
    </div>
  );
}

export default CounterPage;
