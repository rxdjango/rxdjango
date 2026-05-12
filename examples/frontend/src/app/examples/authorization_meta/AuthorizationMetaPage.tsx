import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { AuthorizationMetaChannel } from '../../rx/authorization_meta/authorization_meta.channels';
import {
  Sections,
  Fields,
  Field,
  Button,
  TextInput,
  Row,
  Note,
} from '../../components/demo';

export function AuthorizationMetaPage() {
  const channel = useChannel(AuthorizationMetaChannel);
  const [password, setPassword] = useState('password');

  return (
    <Sections>
      <div>
        <Note>
          Authorize with a password (authorization meta channel), then use the counter.
        </Note>
        <Row>
          <TextInput
            id="authorization-meta-password"
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

export default AuthorizationMetaPage;
