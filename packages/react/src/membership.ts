/**
 * Client-side membership derivation for `many=True` list fields
 * (ADR-0019, design D2/D3): pure functions over already-serialized flat
 * instance values, evaluated with the same verdicts Django produces for the
 * supported lookups on the server.
 *
 * A datetime condition value is DRF's ISO-8601 rendering of the field
 * (design D3). Two renderings of the same instant can carry different UTC
 * offsets (a DST transition, or a bind-time value serialized under a
 * different offset than a live row's), so `exact`/`gt`/`gte`/`lt`/`lte`
 * against a pair of ISO-8601 date-time strings compares them as instants
 * (epoch millis via `Date.parse`), not lexicographically. A datetime string
 * with no explicit offset (a naive value, or a plain date/time string) has
 * no cross-offset ambiguity to begin with, so it -- like every other
 * string -- still compares lexicographically.
 */

/** Strict ISO-8601 date-time detection, offset required: only a value that
 * *carries* a UTC offset (`Z` or `±HH:MM`/`±HHMM`) can disagree with another
 * rendering of the same instant, which is the only case that needs instant
 * comparison instead of lexicographic. */
const ISO_DATETIME_WITH_OFFSET_RE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})$/;

function isIsoDateTimeWithOffset(value: unknown): value is string {
  return typeof value === 'string' && ISO_DATETIME_WITH_OFFSET_RE.test(value);
}

/** `Date.parse` of both operands when both are offset-bearing ISO-8601
 * date-time strings representing the same kind of value; `null` when the
 * instant comparison doesn't apply (fall back to the caller's normal
 * comparison). */
function parseAsInstants(a: unknown, b: unknown): [number, number] | null {
  if (!isIsoDateTimeWithOffset(a) || !isIsoDateTimeWithOffset(b)) return null;
  const parsedA = Date.parse(a);
  const parsedB = Date.parse(b);
  if (Number.isNaN(parsedA) || Number.isNaN(parsedB)) return null;
  return [parsedA, parsedB];
}

/** One introspected `(column, lookup, value)` condition, wire shape per
 * `wire-protocol`'s `q` slot. */
export type ConditionTriple = [string, string, unknown];

/** The bind descriptor riding a `many=True` field's snapshot anchor frame.
 * `l` (ADR-0018 design D5) marks a *routed* (live) field: its membership
 * basis may grow from qualifying full-layer events, not just shrink. Absent
 * (or `false`) on a static field, which keeps cycle 1's never-grow rule. */
export interface QueryDescriptor {
  w: ConditionTriple[];
  s: string[];
  l?: boolean;
}

export const SUPPORTED_LOOKUPS = new Set([
  'exact', 'in', 'gt', 'gte', 'lt', 'lte', 'isnull',
]);

/** Every condition must pass (conjunction) for `instance` to be a member. */
export function evaluateConditions(
  instance: Record<string, unknown>,
  conditions: ConditionTriple[],
): boolean {
  for (const [column, lookup, value] of conditions) {
    if (!evaluateLookup(instance[column], lookup, value)) return false;
  }
  return true;
}

function evaluateLookup(fieldValue: unknown, lookup: string, value: unknown): boolean {
  switch (lookup) {
    case 'isnull':
      return (fieldValue === null || fieldValue === undefined) === (value as boolean);
    case 'exact': {
      const instants = parseAsInstants(fieldValue, value);
      if (instants !== null) return instants[0] === instants[1];
      return fieldValue === value;
    }
    case 'in':
      return Array.isArray(value) && (value as unknown[]).includes(fieldValue);
    case 'gt':
    case 'gte':
    case 'lt':
    case 'lte':
      // Django's NULL comparisons are never true under gt/gte/lt/lte; a
      // residual field that hasn't arrived (or is explicitly null) can't
      // satisfy an ordering-style condition either.
      if (fieldValue === null || fieldValue === undefined) return false;
      return compareLookup(lookup, fieldValue, value);
    default:
      // Unknown/forward lookup: never match rather than risk over-including
      // a row the server-side introspection would have rejected anyway.
      return false;
  }
}

function compareLookup(lookup: string, fieldValue: unknown, value: unknown): boolean {
  const instants = parseAsInstants(fieldValue, value);
  const a = instants !== null ? instants[0] : (fieldValue as number | string);
  const b = instants !== null ? instants[1] : (value as number | string);
  switch (lookup) {
    case 'gt': return a > b;
    case 'gte': return a >= b;
    case 'lt': return a < b;
    case 'lte': return a <= b;
    default: return false;
  }
}

/**
 * Ordering comparator honoring the `s` spec: `-` prefix for descending,
 * left-to-right multi-column precedence, matching Django's `order_by`.
 */
export function compareByOrdering(
  a: Record<string, unknown>,
  b: Record<string, unknown>,
  ordering: string[],
): number {
  for (const spec of ordering) {
    const descending = spec.startsWith('-');
    const column = descending ? spec.slice(1) : spec;
    const cmp = compareColumn(a[column], b[column]);
    if (cmp !== 0) return descending ? -cmp : cmp;
  }
  return 0;
}

function compareColumn(av: unknown, bv: unknown): number {
  if (av === bv) return 0;
  if (av === null || av === undefined) return -1;
  if (bv === null || bv === undefined) return 1;
  const instants = parseAsInstants(av, bv);
  const a = instants !== null ? instants[0] : (av as number | string);
  const b = instants !== null ? instants[1] : (bv as number | string);
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}
