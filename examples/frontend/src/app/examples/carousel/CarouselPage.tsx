import React from 'react';
import { useChannel } from '@rxdjango/react';
import { CarouselChannel } from '../../rx/carousel/carousel.channels';

export function CarouselPage() {
  const channel = useChannel(CarouselChannel);

  return (
    <div>
      <p>
        Selected: {channel.selected}
      </p>
      <p>
        Fruit: {channel.fruit}
      </p>
      <p>
        First letter: {channel.first_letter}
      </p>
      <button onClick={channel.rotate}>
        Next
      </button>
    </div>
  );
}

export default CarouselPage;
