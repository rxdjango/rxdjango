import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { AuthorizationChannel } from '../../rx/authorization/authorization.channels';

export function AuthorizationPage() {
  const channel = useChannel(AuthorizationChannel);
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

export default AuthorizationPage;
