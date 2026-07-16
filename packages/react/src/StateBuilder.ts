/**
 * Rebuilds a nested instance from the flat layers sent by the backend.
 *
 * The Python ``StateModel`` flattens a nested ``ModelSerializer`` into a
 * list of dicts, each tagged with ``_type``. ``StateBuilder`` keeps the
 * latest flat copy of each instance keyed by ``_type:id`` and follows the
 * relation map produced at compile time to splice them back into the
 * nested shape declared by the serializer tree.
 *
 * Built objects are cached per instance and invalidated upward through
 * the relation graph, so an update allocates new objects only along the
 * changed path: untouched instances keep their references, an instance
 * referenced from two relations is the same object in both, and ``state``
 * is reference-stable between updates. React rendering (``memo``,
 * ``useSyncExternalStore``) depends on this contract.
 *
 * Layers from reactive models carry a ``_v`` version. Because the server
 * subscribes to the event stream before fetching the initial snapshot, a
 * snapshot layer can arrive *after* a newer event for the same row. Indexing
 * by arrival order would let the stale snapshot overwrite live state, so
 * ``update`` reconciles by version: a layer is applied only if its ``_v``
 * exceeds the high-water mark already seen for its key. Delete events
 * (``_del``) leave a tombstone — the watermark is retained so a late snapshot
 * of the deleted row cannot resurrect it. Layers with no ``_v`` come from
 * non-reactive models, which emit no events, and are always applied.
 *
 * For a `many=True` list field (ADR-0019, design D2), the same index and
 * cache back a *membership basis* instead of a single anchor key: the
 * server-carried set of anchor pks from the last snapshot (`q` frame, design
 * D1). Derived list state is a pure function of (basis, index, descriptor):
 * basis rows passing the descriptor's `w` conditions, sorted by its `s`
 * spec. The basis is reset atomically by a `q` frame, demoting absent rows
 * without touching their retained `_v` watermarks (they cannot be
 * resurrected by a stale frame), and shrunk by `_del` through the existing
 * detach path; it otherwise never grows -- a mutable residual column
 * flipping toggles *derived* membership via an ordinary update frame, with
 * no change to the basis itself.
 */

import {
  compareByOrdering,
  evaluateConditions,
  type QueryDescriptor,
} from './membership';

export type { QueryDescriptor } from './membership';

export type RelationMap = Record<string, string>;
export type Model = Record<string, RelationMap>;

/** Shared unloaded-relation shape (design D5). Generated relation types are
 * a discriminated union `X | Unloaded` (`_loaded: true` on `X`, `false`
 * here) so `if (x._loaded)` narrows both branches with no cast. */
export interface Unloaded {
  id: number;
  _loaded: false;
}

/** `{ id, _loaded: false }` stub for a `${type}:${id}` index key with no
 * arrived instance yet. The server never sends this shape (design D4); it is
 * constructed purely from the pk the referencing layer already carries. */
function makeStub(key: string): Unloaded {
  const idPart = key.slice(key.indexOf(":") + 1);
  return { id: Number(idPart), _loaded: false };
}

interface FlatInstance {
  _type: string;
  _del?: number;
  id?: number;
  _v?: number;
  [key: string]: unknown;
}

export class StateBuilder<T> {
  private model: Model;
  private anchor: string;
  private many: boolean;
  private index: Record<string, FlatInstance> = {};
  private built = new Map<string, Record<string, unknown> | Unloaded>();
  private parents = new Map<string, Set<string>>();
  private watermark: Record<string, number> = {};
  private anchorKey: string | null = null;

  // -- `many=True` list-field state (design D2) --
  /** Membership basis: anchor pks of the last snapshot. `null` before any
   * `q` frame has arrived -- distinguishes "not yet snapshotted" (`state`
   * is `null`) from "snapshotted empty" (`state` is `[]`). */
  private basis: Set<string> | null = null;
  private descriptor: QueryDescriptor | null = null;
  private derivedKeys: string[] = [];
  private derivedArray: unknown[] | null = null;
  /** Set from the descriptor's `l` marker (ADR-0018 design D5): a live
   * (routed) field's basis grows from qualifying full anchor-type layers;
   * a static field never sets this and keeps the never-grow rule. */
  private live = false;

  constructor(model: Model, anchor: string, many = false) {
    this.model = model;
    this.anchor = anchor;
    this.many = many;
  }

  update(instances: FlatInstance[], query?: QueryDescriptor): void {
    if (query !== undefined) {
      // Bind descriptor on the snapshot anchor frame (ADR-0019 D1): reset
      // the basis atomically to exactly this frame's rows, before merging
      // them -- demoted keys keep their retained watermarks in `index`, just
      // dropped from the basis, so a stale frame can never resurrect them
      // (the watermark check below still applies to their data, unchanged).
      this.descriptor = query;
      this.live = query.l === true;
      const nextBasis = new Set<string>();
      for (const instance of instances) {
        const id = instance.id ?? instance._del;
        if (id === undefined) continue;
        nextBasis.add(`${instance._type}:${id}`);
      }
      this.basis = nextBasis;
    }

    for (const instance of instances) {
      const id = instance.id ?? instance._del;
      const key = id === undefined ? instance._type : `${instance._type}:${id}`;

      const version = instance._v;
      if (version !== undefined) {
        const mark = this.watermark[key];
        if (mark !== undefined && version <= mark) {
          // Stale snapshot layer or already-seen event — discard.
          continue;
        }
        this.watermark[key] = version;
      }

      if (instance._del !== undefined) {
        // Tombstone: `remove` drops the row (and the basis membership, if
        // any) and detaches it from parents, while its watermark is
        // retained so a stale snapshot arriving afterwards is discarded by
        // the version check above.
        this.remove(key);
        continue;
      }

      this.relink(key, this.index[key], instance);
      this.index[key] = instance;
      this.invalidate(key);
      if (!this.many && instance._type === this.anchor && this.anchorKey === null) {
        this.anchorKey = key;
      }
      if (
        this.many &&
        this.live &&
        this.basis !== null &&
        instance._type === this.anchor &&
        !this.basis.has(key) &&
        evaluateConditions(instance, this.descriptor?.w ?? [])
      ) {
        // Basis growth (ADR-0018 design D5): a full anchor-type layer that
        // passes the descriptor's conditions joins the basis -- the leave
        // edge needs no new machinery, since the old-side update frame that
        // disqualifies a member is an ordinary merge frame `deriveList`
        // already re-evaluates on every call.
        this.basis.add(key);
      }
    }

    if (this.many) {
      // Re-derive on every call (design D2: a `q` frame, any merge frame
      // touching a basis row, or a `_del` on one -- deriving unconditionally
      // is simpler and just as correct, since re-deriving is O(basis size)
      // and `rebuild()`'s own cache keeps it cheap).
      this.deriveList();
    }
  }

  get state(): T | null {
    if (this.many) {
      if (this.basis === null) return null;
      return this.derivedArray as T | null;
    }
    if (this.anchorKey === null) return null;
    return this.rebuild(this.anchorKey) as T | null;
  }

  /** Recompute the derived list: basis rows passing the descriptor's `w`
   * conditions, sorted by its `s` spec. Allocates a new array only when the
   * membership/order sequence or an element's own reference changed;
   * unaffected elements (and, when nothing changed, the array itself) keep
   * their prior identity. */
  private deriveList(): void {
    if (this.basis === null) return;

    const conditions = this.descriptor?.w ?? [];
    const ordering = this.descriptor?.s ?? [];

    let keys = Array.from(this.basis).filter((key) => {
      const instance = this.index[key];
      return instance !== undefined && evaluateConditions(instance, conditions);
    });

    if (ordering.length > 0) {
      keys = keys.sort((a, b) =>
        compareByOrdering(this.index[a]!, this.index[b]!, ordering),
      );
    }

    const elements = keys.map((key) => this.rebuild(key));

    let unchanged =
      this.derivedArray !== null && keys.length === this.derivedKeys.length;
    if (unchanged) {
      for (let i = 0; i < keys.length; i++) {
        if (
          keys[i] !== this.derivedKeys[i] ||
          elements[i] !== this.derivedArray![i]
        ) {
          unchanged = false;
          break;
        }
      }
    }

    if (!unchanged) {
      this.derivedKeys = keys;
      this.derivedArray = elements;
    }
  }

  private rebuild(key: string): Record<string, unknown> | Unloaded | null {
    const cached = this.built.get(key);
    if (cached !== undefined) return cached;
    const instance = this.index[key];
    if (instance === undefined) {
      // Referenced but not yet arrived: a memoized stub, not `null` (design
      // D4 / ADR-0016 decision 3). Caching it in `built` under the same key
      // `update()` invalidates on arrival gives it the same identity
      // stability as a built instance, and the existing invalidate/parents
      // propagation replaces it with the real instance for free once that
      // arrival happens -- no separate stub-tracking needed.
      const stub = makeStub(key);
      this.built.set(key, stub);
      return stub;
    }
    const relations = this.model[instance._type] ?? {};
    const out: Record<string, unknown> = {};
    for (const [field, value] of Object.entries(instance)) {
      if (field.startsWith("_")) continue;
      const childType = relations[field];
      if (childType === undefined) {
        out[field] = value;
        continue;
      }
      if (Array.isArray(value)) {
        out[field] = value.map((id) => this.rebuild(`${childType}:${id}`));
      } else if (value === null || value === undefined) {
        out[field] = null;
      } else {
        out[field] = this.rebuild(`${childType}:${value}`);
      }
    }
    // Client-side only: the server payload is unchanged (design D5). `x._loaded`
    // is a real discriminant against the stub shape, so callers can narrow
    // with `if (x._loaded)` and no cast.
    out._loaded = true;
    this.built.set(key, out);
    return out;
  }

  /** Keys of every instance a flat instance references through relations. */
  private childKeys(instance: FlatInstance | undefined): string[] {
    if (instance === undefined) return [];
    const relations = this.model[instance._type] ?? {};
    const keys: string[] = [];
    for (const [field, childType] of Object.entries(relations)) {
      const value = instance[field];
      if (Array.isArray(value)) {
        for (const id of value) keys.push(`${childType}:${id}`);
      } else if (value !== null && value !== undefined) {
        keys.push(`${childType}:${value}`);
      }
    }
    return keys;
  }

  /** Replace the reverse edges of `key` after its flat copy changes. */
  private relink(
    key: string,
    before: FlatInstance | undefined,
    after: FlatInstance | undefined,
  ): void {
    for (const childKey of this.childKeys(before)) {
      this.parents.get(childKey)?.delete(key);
    }
    for (const childKey of this.childKeys(after)) {
      let set = this.parents.get(childKey);
      if (set === undefined) {
        set = new Set();
        this.parents.set(childKey, set);
      }
      set.add(key);
    }
  }

  /** Drop the built object of `key` and of everything that contains it. */
  private invalidate(key: string, seen = new Set<string>()): void {
    if (seen.has(key)) return;
    seen.add(key);
    this.built.delete(key);
    for (const parentKey of this.parents.get(key) ?? []) {
      this.invalidate(parentKey, seen);
    }
  }

  private remove(key: string): void {
    const instance = this.index[key];
    if (instance !== undefined) {
      this.relink(key, instance, undefined);
      delete this.index[key];
    }
    this.invalidate(key);
    for (const parentKey of [...(this.parents.get(key) ?? [])]) {
      this.detach(parentKey, key);
    }
    this.parents.delete(key);
    if (key === this.anchorKey) this.anchorKey = null;
    // A `_del` tombstone shrinks the membership basis through this same
    // detach path (design D2) -- the basis otherwise never shrinks except
    // by a fresh `q` reset.
    this.basis?.delete(key);
  }

  /** Rewrite a parent's flat copy so it no longer references `childKey`. */
  private detach(parentKey: string, childKey: string): void {
    const parent = this.index[parentKey];
    if (parent === undefined) return;
    const relations = this.model[parent._type] ?? {};
    const updated: FlatInstance = { ...parent };
    for (const [field, childType] of Object.entries(relations)) {
      const value = updated[field];
      if (Array.isArray(value)) {
        updated[field] = value.filter((id) => `${childType}:${id}` !== childKey);
      } else if (
        value !== null &&
        value !== undefined &&
        `${childType}:${value}` === childKey
      ) {
        updated[field] = null;
      }
    }
    this.relink(parentKey, parent, updated);
    this.index[parentKey] = updated;
    this.invalidate(parentKey);
  }
}

export default StateBuilder;
