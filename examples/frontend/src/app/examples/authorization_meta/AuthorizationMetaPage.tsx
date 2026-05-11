import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { AuthorizationMetaChannel } from '../../rx/authorization_meta/authorization_meta.channels';

export function AuthorizationMetaPage() {
  const channel = useChannel(AuthorizationMetaChannel);
  const [password, setPassword] = useState('password');

  return (
    <div>
      <div>
        <input
          type="text"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <button onClick={() => channel.authorize(password)}>
          authorize
        </button>
      </div>
      <p>
        Value: {channel.counter}
      </p>
      <button onClick={channel.increment}>
        Increment
      </button>
    </div>
  );
}

export default AuthorizationMetaPage;
