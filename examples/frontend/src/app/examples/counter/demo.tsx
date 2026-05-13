import React from 'react';
import { useChannel } from '@rxdjango/react';
import { CounterChannel } from '../../rx/counter/counter.channels';
import { Demo, Fields, Field, Button } from '../../components/demo';

export function CounterDemo() {
  const channel = useChannel(CounterChannel);

  return (
    <Demo>
      <Fields>
        <Field label="Counter value" large>
          {channel.counter}
        </Field>
      </Fields>
      <Button onClick={channel.increment}>
        Increment
      </Button>
    </Demo>
  );
}

export default CounterDemo;
