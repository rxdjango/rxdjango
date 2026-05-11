import React, { ReactNode } from 'react';

export interface UsageShellProps {
  children: ReactNode;
}

/** Wraps demo content — no outer box; column layout lives in Main. */
export function UsageShell({ children }: UsageShellProps) {
  return (
    <div className="min-w-0 px-1 pt-0 sm:px-0 lg:p-6">
      {children}
    </div>
  );
}

export default UsageShell;
