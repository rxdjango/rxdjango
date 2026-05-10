import React from 'react';
import { useChannel } from '@rxdjango/react';
import { CounterChannel } from '../../rx/counter/counter.channels';

export function CounterPage() {
  const channel = useChannel(CounterChannel);

  return (
    <div>
      <p>
        Value: {channel.counter}
      </p>
      <button onClick={() => channel.increment()}>
        Increment
      </button>
    </div>
  );
}

export default CounterPage;
