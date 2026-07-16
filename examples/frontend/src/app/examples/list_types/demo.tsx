import React from 'react';
import { useChannel } from '@rxdjango/react';
import { ListTypesChannel } from '../../rx/list_types/list_types.channels';
import { Demo, Fields, Field, Button, Row, Note } from '../../components/demo';

export function ListTypesDemo() {
  const channel = useChannel(ListTypesChannel);
  const isUnset = channel.optional_numbers === null;

  return (
    <Demo>
      <Fields>
        <Field label="Mixed list (int | str)">
          <ul className="space-y-1">
            {channel.mixed.map((item, index) => (
              <li key={index}>
                <span className="mr-2 text-xs uppercase tracking-wide text-primary-700">
                  {typeof item}
                </span>
                <span>
                  {String(item)}
                </span>
              </li>
            ))}
          </ul>
        </Field>
        <Field label="Optional numbers (list[int] | None)">
          {isUnset ? (
            <Note>
              null (not set)
            </Note>
          ) : (
            <span>
              {channel.optional_numbers!.length === 0
                ? 'empty list'
                : channel.optional_numbers!.join(', ')}
            </span>
          )}
        </Field>
      </Fields>
      <Row>
        <Button onClick={() => channel.add_number(Math.floor(Math.random() * 100))}>
          Add number
        </Button>
        <Button onClick={() => channel.add_text('word')}>
          Add text
        </Button>
        <Button
          variant="secondary"
          onClick={() => channel.clear_mixed()}
        >
          Clear mixed
        </Button>
      </Row>
      <Row>
        <Button onClick={() => channel.set_numbers([1, 2, 3])}>
          Set numbers
        </Button>
        <Button
          variant="secondary"
          onClick={() => channel.append_number(Math.floor(Math.random() * 100))}
          disabled={isUnset}
        >
          Append number
        </Button>
        <Button
          variant="secondary"
          onClick={() => channel.clear_numbers()}
        >
          Clear (empty list)
        </Button>
        <Button
          variant="secondary"
          onClick={() => channel.unset_numbers()}
        >
          Unset (null)
        </Button>
      </Row>
    </Demo>
  );
}

export default ListTypesDemo;
