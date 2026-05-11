import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { AuthorizationMetaChannel } from '../../rx/authorization_meta/authorization_meta.channels';

const primaryButtonClass =
  'inline-flex items-center justify-center rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-600 active:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-surface';

const secondaryButtonClass =
  'inline-flex items-center justify-center rounded-md border border-ink/45 bg-transparent px-4 py-2.5 text-sm font-medium text-primary-800 transition-colors hover:border-ink/70 hover:bg-ink/[0.11] focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-surface';

const inputClass =
  'min-w-0 flex-1 rounded-md border border-ink/40 bg-surface px-3 py-2 text-sm text-ink focus:border-ink/75 focus:outline-none focus:ring-2 focus:ring-primary-500/30';

export function AuthorizationMetaPage() {
  const channel = useChannel(AuthorizationMetaChannel);
  const [password, setPassword] = useState('password');

  return (
    <div className="divide-y divide-ink/58">
      <div className="space-y-4 pb-8">
        <p className="text-sm font-medium text-primary-800">
          Authorize with a password (authorization meta channel), then use the
          counter.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="sr-only" htmlFor="authorization-meta-password">
            Password
          </label>
          <input
            id="authorization-meta-password"
            type="text"
            className={inputClass}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <button
            type="button"
            className={secondaryButtonClass}
            onClick={() => channel.authorize(password)}
          >
            Authorize
          </button>
        </div>
      </div>
      <div className="space-y-6 pt-8">
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
    </div>
  );
}

export default AuthorizationMetaPage;
