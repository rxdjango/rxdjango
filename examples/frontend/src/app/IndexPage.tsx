import React from 'react';

interface IndexPageProps {
  onSelectCounter: () => void;
}

export function IndexPage({ onSelectCounter }: IndexPageProps) {
  return (
    <div>
      <h1>RxDjango Demo</h1>
      <p>
        A collection of small examples that show how RxDjango keeps a React UI
        in sync with a Django backend through reactive channels. Pick an example
        below to see it in action.
      </p>
      <ul>
        <li>
          <a
            href="#counter"
            onClick={(event) => {
              event.preventDefault();
              onSelectCounter();
            }}
          >
            Counter
          </a>
        </li>
      </ul>
    </div>
  );
}

export default IndexPage;
