import React from 'react';
import { useChannel } from '@rxdjango/react';
import { StreamingListChannel } from '../../rx/streaming_list/streaming_list.channels';
import { Demo, Fields, Field, Button, Row, Note } from '../../components/demo';

export function StreamingListDemo() {
  const channel = useChannel(StreamingListChannel);

  return (
    <Demo>
      <Fields>
        <Field label="Streamed items">
          <ul className="flex flex-wrap gap-2">
            {channel.items.map((item, index) => (
              <li
                key={index}
                className="rounded-md border border-ink/40 px-2 py-1 text-sm tabular-nums"
              >
                {item}
              </li>
            ))}
          </ul>
        </Field>
      </Fields>
      <Note>
        A background timer appends one number every tick — no page reload,
        no full re-send, just a small insert op per item.
      </Note>
      <Row>
        {channel.ticking ? (
          <Button variant="secondary" onClick={() => channel.pause()}>
            Pause
          </Button>
        ) : (
          <Button onClick={() => channel.resume()}>
            Resume
          </Button>
        )}
        <Button variant="secondary" onClick={() => channel.reset()}>
          Reset
        </Button>
      </Row>
    </Demo>
  );
}

export default StreamingListDemo;
