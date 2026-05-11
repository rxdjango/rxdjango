import React from 'react';
import { useChannel } from '@rxdjango/react';
import { CarouselMemoChannel } from '../../rx/memo/memo.channels';

export function MemoPage() {
  const channel = useChannel(CarouselMemoChannel);

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

export default MemoPage;
