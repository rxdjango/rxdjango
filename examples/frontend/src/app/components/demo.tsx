import React, { ReactNode } from 'react';

const primaryButtonClass =
  'inline-flex items-center justify-center rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-600 active:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-surface';

const secondaryButtonClass =
  'inline-flex items-center justify-center rounded-md border border-ink/45 bg-transparent px-4 py-2.5 text-sm font-medium text-primary-800 transition-colors hover:border-ink/70 hover:bg-ink/[0.11] focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-surface';

const inputClass =
  'min-w-0 flex-1 rounded-md border border-ink/40 bg-surface px-3 py-2 text-sm text-ink focus:border-ink/75 focus:outline-none focus:ring-2 focus:ring-primary-500/30';

export function Demo({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      {children}
    </div>
  );
}

export function Sections({ children }: { children: ReactNode }) {
  return (
    <div className="divide-y divide-ink/58 [&>*]:py-8 [&>*:first-child]:pt-0 [&>*:last-child]:pb-0 [&>*]:space-y-6">
      {children}
    </div>
  );
}

export function Field({
  label,
  large,
  children,
}: {
  label: string;
  large?: boolean;
  children: ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-primary-700">
        {label}
      </dt>
      <dd
        className={
          large
            ? 'mt-1 text-2xl font-semibold tabular-nums text-ink'
            : 'mt-1 text-lg font-medium text-ink'
        }
      >
        {children}
      </dd>
    </div>
  );
}

export function Fields({ children }: { children: ReactNode }) {
  return (
    <dl className="space-y-4">
      {children}
    </dl>
  );
}

export function Button({
  onClick,
  variant = 'primary',
  disabled,
  children,
}: {
  onClick: () => void;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className={variant === 'primary' ? primaryButtonClass : secondaryButtonClass}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export function TextInput({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <>
      <label className="sr-only" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type="text"
        className={inputClass}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </>
  );
}

export function Row({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      {children}
    </div>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return (
    <p className="text-sm font-medium text-primary-800">
      {children}
    </p>
  );
}
