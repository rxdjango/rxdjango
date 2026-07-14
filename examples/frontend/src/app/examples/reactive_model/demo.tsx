import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { ReactiveModelChannel } from '../../rx/reactive_model/reactive_model.channels';
import {
  Sections,
  Button,
  TextInput,
  Row,
  Note,
  Field,
  Fields,
} from '../../components/demo';

export function ReactiveModelDemo() {
  const channel = useChannel(ReactiveModelChannel);
  const [projectName, setProjectName] = useState('');
  const [delay, setDelay] = useState('2');

  return (
    <Sections>
      <div>
        <Note>
          Modify the project name with a delay. The update happens in a background
          thread outside the channel context, demonstrating that external changes
          to a model instance are pushed reactively to the frontend.
        </Note>
        <Row>
          <TextInput
            id="reactive-model-project-name"
            label="New project name"
            value={projectName}
            onChange={setProjectName}
          />
          <TextInput
            id="reactive-model-delay"
            label="Delay (seconds)"
            value={delay}
            onChange={setDelay}
          />
          <Button
            variant="secondary"
            onClick={() => channel.modify_project(projectName, parseInt(delay, 10))}
          >
            Modify
          </Button>
        </Row>
      </div>
      <div>
        {channel.task ? (
          <Fields>
            <Field label="Task">
              {channel.task.name}
            </Field>
            <Field label="Project">
              {channel.task.project._loaded
                ? channel.task.project.name
                : 'Loading…'}
            </Field>
          </Fields>
        ) : (
          <p>
            Connecting...
          </p>
        )}
      </div>
    </Sections>
  );
}

export default ReactiveModelDemo;
