import React from 'react';

interface IndexPageProps {
  onSelect: (name: 'counter' | 'carousel') => void;
}

export function IndexPage({ onSelect }: IndexPageProps) {
  return (
    <div>
      <h1>
        RxDjango Demo
      </h1>
      <p>
        A collection of small examples that show how RxDjango keeps a React UI
        in sync with a Django backend through reactive channels. Pick an example
        below to see it in action.
      </p>
      <ul>
        <li>
          <a
            href="/counter"
            onClick={(event) => {
              event.preventDefault();
              onSelect('counter');
            }}
          >
            Counter
          </a>
        </li>
        <li>
          <a
            href="/carousel"
            onClick={(event) => {
              event.preventDefault();
              onSelect('carousel');
            }}
          >
            Carousel
          </a>
        </li>
      </ul>
    </div>
  );
}

export default IndexPage;
