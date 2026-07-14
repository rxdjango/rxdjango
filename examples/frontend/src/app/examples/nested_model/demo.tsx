import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { NestedModelChannel } from '../../rx/nested_model/nested_model.channels';
import {
  Sections,
  Button,
  TextInput,
  Row,
  Note,
} from '../../components/demo';

export function NestedModelDemo() {
  const channel = useChannel(NestedModelChannel);
  const [password, setPassword] = useState('password');

  return (
    <Sections>
      <div>
        <Note>
          Authorize with a password to load the user model along with its nested company.
        </Note>
        <Row>
          <TextInput
            id="nested-model-password"
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
            You are user "{channel.user.name}" at "
            {channel.user.company._loaded
              ? channel.user.company.name
              : 'Loading…'}"
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

export default NestedModelDemo;
