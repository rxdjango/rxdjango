import React from 'react';
import { useChannel } from '@rxdjango/react';
import { CarouselMemoChannel } from '../../rx/memo/memo.channels';
import { Demo, Fields, Field, Button } from '../../components/demo';

export function MemoDemo() {
  const channel = useChannel(CarouselMemoChannel);

  return (
    <Demo>
      <Fields>
        <Field label="Selected">
          {channel.selected}
        </Field>
        <Field label="Fruit">
          {channel.fruit}
        </Field>
        <Field label="First letter">
          {channel.first_letter}
        </Field>
      </Fields>
      <Button onClick={channel.rotate}>
        Next
      </Button>
    </Demo>
  );
}

export default MemoDemo;
