import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { AuthorizationChannel } from '../../rx/authorization/authorization.channels';
import {
  Sections,
  Fields,
  Field,
  Button,
  TextInput,
  Row,
  Note,
} from '../../components/demo';

export function AuthorizationDemo() {
  const channel = useChannel(AuthorizationChannel);
  const [password, setPassword] = useState('password');

  return (
    <Sections>
      <div>
        <Note>
          Authorize with a password, then use the counter.
        </Note>
        <Row>
          <TextInput
            id="authorization-password"
            label="Password"
            value={password}
            onChange={setPassword}
          />
          <Button
            variant="secondary"
            onClick={() => channel.authorize(password)}
          >
            Authorize
          </Button>
        </Row>
      </div>
      <div>
        <Fields>
          <Field label="Counter value" large>
            {channel.counter}
          </Field>
        </Fields>
        <Button onClick={channel.increment}>
          Increment
        </Button>
      </div>
    </Sections>
  );
}

export default AuthorizationDemo;
