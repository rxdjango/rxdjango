/**
 * Client-side membership derivation for `many=True` list fields
 * (ADR-0019, design D2/D3): pure functions over already-serialized flat
 * instance values, evaluated with the same verdicts Django produces for the
 * supported lookups on the server.
 *
 * A datetime condition value is DRF's ISO-8601 rendering of the field
 * (design D3), so `gt`/`gte`/`lt`/`lte` against it is a plain string
 * comparison -- correct as long as every datetime on the wire is rendered
 * with a uniform offset, which is a deployment-level assumption this module
 * does not itself verify.
 */

/** One introspected `(column, lookup, value)` condition, wire shape per
 * `wire-protocol`'s `q` slot. */
export type ConditionTriple = [string, string, unknown];

/** The bind descriptor riding a `many=True` field's snapshot anchor frame. */
export interface QueryDescriptor {
  w: ConditionTriple[];
  s: string[];
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
    case 'exact':
      return fieldValue === value;
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
  const a = fieldValue as number | string;
  const b = value as number | string;
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
  const a = av as number | string;
  const b = bv as number | string;
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}
