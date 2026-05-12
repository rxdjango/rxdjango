import React from 'react';
import { MemoDemo } from './demo';
import {
  ExampleLayout,
  ExampleSection,
  ExampleSectionHeading,
  ExampleDescription,
  ExampleClientBadge,
} from '../../components/ExampleLayout';
import { SourceFile } from '../../components/SourceFile';

export function MemoPage() {
  return (
    <ExampleLayout title="Memo" demo={<MemoDemo />}>
      <ExampleSection position="first">
        <ExampleDescription>
          Same interaction as Carousel, but fruit and first letter are derived
          with @memo from selected. Useful when you want stable derived values
          and explicit dependency tracking on the channel.
        </ExampleDescription>
      </ExampleSection>
      <ExampleSection ariaLabelledBy="memo-backend">
        <ExampleSectionHeading id="memo-backend">
          Backend
        </ExampleSectionHeading>
        <SourceFile path="memo/channels.py" />
      </ExampleSection>
      <ExampleSection ariaLabelledBy="memo-frontend" position="last">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <ExampleSectionHeading id="memo-frontend">
            Frontend
          </ExampleSectionHeading>
          <ExampleClientBadge />
        </div>
        <SourceFile path="memo/demo.tsx" />
      </ExampleSection>
    </ExampleLayout>
  );
}

export default MemoPage;
