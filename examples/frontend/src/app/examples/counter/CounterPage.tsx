import React from 'react';
import { useChannel } from '@rxdjango/react';
import { CounterChannel } from '../../rx/counter/counter.channels';

const primaryButtonClass =
  'inline-flex items-center justify-center rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-600 active:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-surface';

export function CounterPage() {
  const channel = useChannel(CounterChannel);

  return (
    <div className="space-y-6">
      <dl className="space-y-4">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-primary-700">
            Counter value
          </dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-ink">
            {channel.counter}
          </dd>
        </div>
      </dl>
      <div>
        <button
          type="button"
          className={primaryButtonClass}
          onClick={channel.increment}
        >
          Increment
        </button>
      </div>
    </div>
  );
}

export default CounterPage;
