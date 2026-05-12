import React from 'react';
import { AuthorizationDemo } from './demo';
import {
  ExampleLayout,
  ExampleSection,
  ExampleSectionHeading,
  ExampleDescription,
  ExampleClientBadge,
} from '../../components/ExampleLayout';
import { SourceFile } from '../../components/SourceFile';

export function AuthorizationPage() {
  return (
    <ExampleLayout title="Authorization" demo={<AuthorizationDemo />}>
      <ExampleSection position="first">
        <ExampleDescription>
          increment is declared with requires authorized; authorize checks the
          password and sets a flag. Until you authorize successfully, the
          increment action will not run—per-action authorization on the channel.
        </ExampleDescription>
      </ExampleSection>
      <ExampleSection ariaLabelledBy="authorization-backend">
        <ExampleSectionHeading id="authorization-backend">
          Backend
        </ExampleSectionHeading>
        <SourceFile path="authorization/channels.py" />
      </ExampleSection>
      <ExampleSection ariaLabelledBy="authorization-frontend" position="last">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <ExampleSectionHeading id="authorization-frontend">
            Frontend
          </ExampleSectionHeading>
          <ExampleClientBadge />
        </div>
        <SourceFile path="authorization/demo.tsx" />
      </ExampleSection>
    </ExampleLayout>
  );
}

export default AuthorizationPage;
