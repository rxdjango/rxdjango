import React, { ReactNode } from 'react';
import { UsageShell } from '../UsageShell';

const sectionHeadingClass =
  'text-xs font-medium uppercase tracking-wide text-primary-700';

const usageHeadingClass = `${sectionHeadingClass} border-b border-ink/58 mb-2 p-4`;

export function ExampleSectionHeading({
  id,
  children,
}: {
  id?: string;
  children: ReactNode;
}) {
  return (
    <h2 id={id} className={sectionHeadingClass}>
      {children}
    </h2>
  );
}

export function ExampleDescription({ children }: { children: ReactNode }) {
  return (
    <p className="text-sm leading-relaxed text-primary-800">
      {children}
    </p>
  );
}

export function ExampleSection({
  ariaLabelledBy,
  position,
  children,
}: {
  ariaLabelledBy?: string;
  position?: 'first' | 'middle' | 'last';
  children: ReactNode;
}) {
  const padding =
    position === 'first'
      ? 'pb-8'
      : position === 'last'
      ? 'pt-8'
      : 'py-8';
  return (
    <section
      aria-labelledby={ariaLabelledBy}
      className={`space-y-2 ${padding}`}
    >
      {children}
    </section>
  );
}

export function ExampleClientBadge() {
  return (
    <div
      className="inline-flex shrink-0 rounded-md border border-ink/42 bg-surface p-0.5"
      aria-label="Client package: React"
    >
      <span className="min-w-[5.5rem] rounded px-2.5 py-1.5 text-left text-xs font-medium bg-primary-500 text-white">
        <span className="block leading-tight">
          React
        </span>
        <span className="mt-0.5 block text-[10px] font-normal leading-tight opacity-90">
          @rxdjango/react
        </span>
      </span>
    </div>
  );
}

export function ExampleLayout({
  title,
  demo,
  children,
}: {
  title: string;
  demo: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto flex w-full min-h-0 max-w-8xl flex-1 flex-col px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">
        {title}
      </h1>
      <div className="mt-6 grid min-h-0 w-full flex-1 grid-cols-1 gap-0 divide-y divide-ink/68 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-stretch lg:gap-12 lg:divide-y-0">
        <div
          className="flex min-h-0 min-w-0 flex-col divide-y divide-ink/68 pb-10 lg:overflow-y-auto lg:overscroll-y-contain lg:border-r lg:border-ink/68 lg:pb-0 lg:pr-10"
          aria-label="Documentation"
        >
          {children}
        </div>
        <div className="flex min-h-0 min-w-0 w-full flex-col pt-10 lg:pt-0">
          <div className="flex min-h-0 w-full flex-1 flex-col rounded-lg bg-white shadow-md lg:z-10 lg:max-w-full lg:self-stretch lg:shadow-lg">
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-y-contain px-1 pt-0 sm:px-0 lg:p-6">
              <section>
                <h2 className={usageHeadingClass}>
                  Usage
                </h2>
                <UsageShell>
                  {demo}
                </UsageShell>
              </section>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExampleLayout;
