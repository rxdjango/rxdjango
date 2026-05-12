import React from 'react';
import { useChannel } from '@rxdjango/react';
import { CarouselChannel } from '../../rx/carousel/carousel.channels';
import { Demo, Fields, Field, Button } from '../../components/demo';

export function CarouselDemo() {
  const channel = useChannel(CarouselChannel);

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

export default CarouselDemo;
