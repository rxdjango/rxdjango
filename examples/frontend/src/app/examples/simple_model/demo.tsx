import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { SimpleModelChannel } from '../../rx/simple_model/simple_model.channels';
import {
  Sections,
  Button,
  TextInput,
  Row,
  Note,
} from '../../components/demo';

export function SimpleModelDemo() {
  const channel = useChannel(SimpleModelChannel);
  const [password, setPassword] = useState('password');

  return (
    <Sections>
      <div>
        <Note>
          Authorize with a password to load the user model on the channel.
        </Note>
        <Row>
          <TextInput
            id="simple-model-password"
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
        {channel.user ? (
          <p>
            You are user "{channel.user.name}"
          </p>
        ) : (
          <p>
            Enter your password
          </p>
        )}
      </div>
    </Sections>
  );
}

export default SimpleModelDemo;
