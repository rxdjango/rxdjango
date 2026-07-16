import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { ScalarListChannel } from '../../rx/scalar_list/scalar_list.channels';
import { Demo, Fields, Field, Button, TextInput, Row } from '../../components/demo';

export function ScalarListDemo() {
  const channel = useChannel(ScalarListChannel);
  const [draft, setDraft] = useState('');
  const [setIndex, setSetIndex] = useState('0');
  const [setValue, setSetValue] = useState('');

  const appendDraft = () => {
    if (!draft) return;
    channel.append(draft);
    setDraft('');
  };

  return (
    <Demo>
      <Fields>
        <Field label="Items">
          <ul className="space-y-2">
            {channel.items.map((item, index) => (
              <li
                key={`${index}-${item}`}
                className="flex items-center justify-between gap-3"
              >
                <span>
                  {item}
                </span>
                <Button
                  variant="secondary"
                  onClick={() => channel.remove_at(index)}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        </Field>
      </Fields>
      <Row>
        <TextInput
          id="scalar-list-draft"
          label="New item"
          value={draft}
          onChange={setDraft}
        />
        <Button onClick={appendDraft}>
          Append
        </Button>
      </Row>
      <Row>
        <Button onClick={() => channel.insert(0, 'first')}>
          Insert at start
        </Button>
        <Button onClick={() => channel.pop()}>
          Pop last
        </Button>
        <Button variant="secondary" onClick={() => channel.replace_all()}>
          Replace all
        </Button>
      </Row>
      <Row>
        <TextInput
          id="scalar-list-set-index"
          label="Set index"
          value={setIndex}
          onChange={setSetIndex}
        />
        <TextInput
          id="scalar-list-set-value"
          label="Set value"
          value={setValue}
          onChange={setSetValue}
        />
        <Button
          variant="secondary"
          onClick={() => channel.set_at(Number(setIndex), setValue)}
        >
          Set
        </Button>
      </Row>
    </Demo>
  );
}

export default ScalarListDemo;
