import React from 'react';
import { useChannel } from '@rxdjango/react';
import { CarouselChannel } from '../../rx/carousel/carousel.channels';

const primaryButtonClass =
  'inline-flex items-center justify-center rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-600 active:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-surface';

export function CarouselPage() {
  const channel = useChannel(CarouselChannel);

  return (
    <div className="space-y-6">
      <dl className="grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-primary-700">
            Selected
          </dt>
          <dd className="mt-1 text-lg font-medium text-ink">
            {channel.selected}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-primary-700">
            Fruit
          </dt>
          <dd className="mt-1 text-lg font-medium text-ink">
            {channel.fruit}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs font-medium uppercase tracking-wide text-primary-700">
            First letter
          </dt>
          <dd className="mt-1 text-lg font-medium text-ink">
            {channel.first_letter}
          </dd>
        </div>
      </dl>
      <div>
        <button
          type="button"
          className={primaryButtonClass}
          onClick={channel.rotate}
        >
          Next
        </button>
      </div>
    </div>
  );
}

export default CarouselPage;
