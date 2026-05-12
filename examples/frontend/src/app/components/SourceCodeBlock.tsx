import React from 'react';

export type Language = 'python' | 'typescript';

interface Token {
  type:
    | 'keyword'
    | 'builtin'
    | 'decorator'
    | 'string'
    | 'comment'
    | 'number'
    | 'tag'
    | 'attr'
    | 'default';
  value: string;
}

// One Dark Pro palette
const TOKEN_COLORS: Record<Token['type'], string> = {
  keyword: '#c678dd',
  builtin: '#61afef',
  decorator: '#e5c07b',
  string: '#98c379',
  comment: '#5c6370',
  number: '#d19a66',
  tag: '#e06c75',
  attr: '#d19a66',
  default: '#abb2bf',
};

const PY_KEYWORDS = new Set([
  'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
  'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
  'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
  'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'self',
  'try', 'while', 'with', 'yield',
]);

const PY_BUILTINS = new Set([
  'abs', 'all', 'any', 'bool', 'callable', 'classmethod', 'dict',
  'enumerate', 'filter', 'float', 'getattr', 'hasattr', 'int', 'isinstance',
  'issubclass', 'len', 'list', 'map', 'max', 'min', 'object', 'open',
  'print', 'property', 'range', 'reversed', 'set', 'setattr', 'sorted',
  'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'zip',
]);

const TS_KEYWORDS = new Set([
  'abstract', 'any', 'as', 'async', 'await', 'boolean', 'break', 'case',
  'catch', 'class', 'const', 'continue', 'declare', 'default', 'delete',
  'do', 'else', 'enum', 'export', 'extends', 'false', 'finally', 'for',
  'from', 'function', 'if', 'implements', 'import', 'in', 'instanceof',
  'interface', 'keyof', 'let', 'namespace', 'never', 'new', 'null',
  'number', 'of', 'private', 'protected', 'public', 'readonly', 'return',
  'static', 'string', 'super', 'switch', 'this', 'throw', 'true', 'try',
  'type', 'typeof', 'undefined', 'var', 'void', 'while', 'yield',
]);

function tokenizePython(src: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;

  while (i < src.length) {
    // Triple-quoted strings
    const tripleDouble = src.slice(i, i + 3);
    if (tripleDouble === '"""' || tripleDouble === "'''") {
      const q = tripleDouble;
      const end = src.indexOf(q, i + 3);
      const close = end === -1 ? src.length : end + 3;
      tokens.push({ type: 'string', value: src.slice(i, close) });
      i = close;
      continue;
    }

    // Line comment
    if (src[i] === '#') {
      const nl = src.indexOf('\n', i);
      const end = nl === -1 ? src.length : nl;
      tokens.push({ type: 'comment', value: src.slice(i, end) });
      i = end;
      continue;
    }

    // Decorator
    if (src[i] === '@') {
      const m = src.slice(i).match(/^@[A-Za-z_]\w*(\.[A-Za-z_]\w*)*/);
      if (m) {
        tokens.push({ type: 'decorator', value: m[0] });
        i += m[0].length;
        continue;
      }
    }

    // String literals
    if (src[i] === '"' || src[i] === "'") {
      const q = src[i];
      let j = i + 1;
      while (j < src.length && src[j] !== q && src[j] !== '\n') {
        if (src[j] === '\\') j++;
        j++;
      }
      const end = j < src.length ? j + 1 : j;
      tokens.push({ type: 'string', value: src.slice(i, end) });
      i = end;
      continue;
    }

    // Number
    if (/\d/.test(src[i]) && (i === 0 || !/[A-Za-z_]/.test(src[i - 1]))) {
      const m = src.slice(i).match(/^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/);
      if (m) {
        tokens.push({ type: 'number', value: m[0] });
        i += m[0].length;
        continue;
      }
    }

    // Identifier
    if (/[A-Za-z_]/.test(src[i])) {
      const m = src.slice(i).match(/^[A-Za-z_]\w*/);
      if (m) {
        const word = m[0];
        const type: Token['type'] = PY_KEYWORDS.has(word)
          ? 'keyword'
          : PY_BUILTINS.has(word)
          ? 'builtin'
          : 'default';
        tokens.push({ type, value: word });
        i += word.length;
        continue;
      }
    }

    tokens.push({ type: 'default', value: src[i] });
    i++;
  }

  return tokens;
}

function tokenizeTypeScript(src: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;

  while (i < src.length) {
    // Block comment
    if (src.slice(i, i + 2) === '/*') {
      const end = src.indexOf('*/', i + 2);
      const close = end === -1 ? src.length : end + 2;
      tokens.push({ type: 'comment', value: src.slice(i, close) });
      i = close;
      continue;
    }

    // Line comment
    if (src.slice(i, i + 2) === '//') {
      const nl = src.indexOf('\n', i);
      const end = nl === -1 ? src.length : nl;
      tokens.push({ type: 'comment', value: src.slice(i, end) });
      i = end;
      continue;
    }

    // Template literal
    if (src[i] === '`') {
      let j = i + 1;
      let depth = 0;
      while (j < src.length) {
        if (src[j] === '\\') { j += 2; continue; }
        if (src.slice(j, j + 2) === '${') { depth++; j += 2; continue; }
        if (src[j] === '}' && depth > 0) { depth--; j++; continue; }
        if (src[j] === '`' && depth === 0) { j++; break; }
        j++;
      }
      tokens.push({ type: 'string', value: src.slice(i, j) });
      i = j;
      continue;
    }

    // String literals
    if (src[i] === '"' || src[i] === "'") {
      const q = src[i];
      let j = i + 1;
      while (j < src.length && src[j] !== q && src[j] !== '\n') {
        if (src[j] === '\\') j++;
        j++;
      }
      const end = j < src.length ? j + 1 : j;
      tokens.push({ type: 'string', value: src.slice(i, end) });
      i = end;
      continue;
    }

    // JSX closing tag </Foo> or self-close />
    if (src.slice(i, i + 2) === '</') {
      const m = src.slice(i).match(/^<\/[A-Za-z][A-Za-z0-9.]*\s*>/);
      if (m) {
        tokens.push({ type: 'tag', value: m[0] });
        i += m[0].length;
        continue;
      }
    }

    // JSX opening/self-closing tag <Foo ...> — only if starts with uppercase or known element
    if (src[i] === '<' && i + 1 < src.length && /[A-Za-z]/.test(src[i + 1])) {
      // Scan the whole tag including attributes
      let j = i + 1;
      let inStr: string | null = null;
      while (j < src.length) {
        if (inStr) {
          if (src[j] === inStr) inStr = null;
          j++;
          continue;
        }
        if (src[j] === '"' || src[j] === "'") { inStr = src[j]; j++; continue; }
        if (src[j] === '>') { j++; break; }
        if (src.slice(j, j + 2) === '/>') { j += 2; break; }
        j++;
      }
      const raw = src.slice(i, j);
      // Tokenize the tag internals: tag name, attrs, punctuation
      const tagName = raw.match(/^<\/?([A-Za-z][A-Za-z0-9.]*)/);
      if (tagName) {
        tokens.push({ type: 'tag', value: raw });
        i = j;
        continue;
      }
    }

    // Number
    if (/\d/.test(src[i]) && (i === 0 || !/[A-Za-z_$]/.test(src[i - 1]))) {
      const m = src.slice(i).match(/^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?n?/);
      if (m) {
        tokens.push({ type: 'number', value: m[0] });
        i += m[0].length;
        continue;
      }
    }

    // Identifier
    if (/[A-Za-z_$]/.test(src[i])) {
      const m = src.slice(i).match(/^[A-Za-z_$][\w$]*/);
      if (m) {
        const word = m[0];
        const type: Token['type'] = TS_KEYWORDS.has(word) ? 'keyword' : 'default';
        tokens.push({ type, value: word });
        i += word.length;
        continue;
      }
    }

    tokens.push({ type: 'default', value: src[i] });
    i++;
  }

  return tokens;
}

function tokenize(src: string, lang: Language): Token[] {
  return lang === 'python' ? tokenizePython(src) : tokenizeTypeScript(src);
}

export function SourceCodeBlock({
  code,
  language,
}: {
  code: string;
  language: Language;
}) {
  const tokens = tokenize(code, language);
  const lines: Token[][] = [[]];

  for (const tok of tokens) {
    const parts = tok.value.split('\n');
    for (let p = 0; p < parts.length; p++) {
      if (p > 0) lines.push([]);
      if (parts[p].length > 0) {
        lines[lines.length - 1].push({ type: tok.type, value: parts[p] });
      }
    }
  }

  return (
    <div
      className="mt-2 overflow-x-auto rounded-md border border-ink/50 font-mono text-xs leading-relaxed"
      style={{ backgroundColor: '#282c34' }}
      role="region"
      aria-label="Source code"
    >
      <div className="flex py-3">
        <div
          aria-hidden="true"
          className="sticky left-0 z-10 shrink-0 select-none border-r py-0 pl-3 pr-4 text-right tabular-nums"
          style={{
            backgroundColor: '#282c34',
            borderColor: 'rgba(255,255,255,0.12)',
            color: 'rgba(171,178,191,0.45)',
          }}
        >
          {lines.map((_, idx) => (
            <div key={idx} className="min-h-[1.375rem]">
              {idx + 1}
            </div>
          ))}
        </div>
        <div className="min-w-0 flex-1 pl-5 pr-4">
          {lines.map((lineTokens, idx) => (
            <div key={idx} className="min-h-[1.375rem] whitespace-pre">
              {lineTokens.length === 0 ? (
                ' '
              ) : (
                lineTokens.map((tok, ti) => (
                  <span key={ti} style={{ color: TOKEN_COLORS[tok.type] }}>
                    {tok.value}
                  </span>
                ))
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
