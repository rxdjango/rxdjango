import React from 'react';
import { CounterDemo } from './demo';
import {
  ExampleLayout,
  ExampleSection,
  ExampleSectionHeading,
  ExampleDescription,
  ExampleClientBadge,
} from '../../components/ExampleLayout';
import { SourceFile } from '../../components/SourceFile';

export function CounterPage() {
  return (
    <ExampleLayout title="Counter" demo={<CounterDemo />}>
      <ExampleSection position="first">
        <ExampleDescription>
          A single reactive integer on the channel. Subscribe from React with
          useChannel, then call increment to run the server-side action and see
          the value update everywhere it is displayed.
        </ExampleDescription>
      </ExampleSection>
      <ExampleSection ariaLabelledBy="counter-backend">
        <ExampleSectionHeading id="counter-backend">
          Backend
        </ExampleSectionHeading>
        <SourceFile path="counter/channels.py" />
      </ExampleSection>
      <ExampleSection ariaLabelledBy="counter-frontend" position="last">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <ExampleSectionHeading id="counter-frontend">
            Frontend
          </ExampleSectionHeading>
          <ExampleClientBadge />
        </div>
        <SourceFile path="counter/demo.tsx" />
      </ExampleSection>
    </ExampleLayout>
  );
}

export default CounterPage;
