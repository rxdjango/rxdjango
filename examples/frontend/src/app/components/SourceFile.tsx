import React, { useEffect, useState } from 'react';
import { SourceCodeBlock, Language } from './SourceCodeBlock';

function languageFromPath(path: string): Language {
  if (path.endsWith('.py')) return 'python';
  return 'typescript';
}

export function SourceFile({
  path,
  language,
}: {
  path: string;
  language?: Language;
}) {
  const [code, setCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCode(null);
    setError(null);

    fetch(`/src/${path}`, { cache: 'no-store' }).then(
      async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          setError(`Failed to load ${path}: ${res.status}`);
          return;
        }
        setCode(await res.text());
      },
      (err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      },
    );

    return () => {
      cancelled = true;
    };
  }, [path]);

  if (error != null) {
    return (
      <p className="mt-2 text-sm leading-relaxed text-primary-700">
        Failed to load source: {error}
      </p>
    );
  }
  if (code == null) {
    return (
      <p className="mt-2 text-sm leading-relaxed text-primary-700">
        Loading…
      </p>
    );
  }
  return (
    <SourceCodeBlock code={code} language={language ?? languageFromPath(path)} />
  );
}

export default SourceFile;
