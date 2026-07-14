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
 */

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
  private index: Record<string, FlatInstance> = {};
  private built = new Map<string, Record<string, unknown> | Unloaded>();
  private parents = new Map<string, Set<string>>();
  private watermark: Record<string, number> = {};
  private anchorKey: string | null = null;

  constructor(model: Model, anchor: string) {
    this.model = model;
    this.anchor = anchor;
  }

  update(instances: FlatInstance[]): void {
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
        // Tombstone: `remove` drops the row and detaches it from parents,
        // while its watermark is retained so a stale snapshot arriving
        // afterwards is discarded by the version check above.
        this.remove(key);
        continue;
      }

      this.relink(key, this.index[key], instance);
      this.index[key] = instance;
      this.invalidate(key);
      if (instance._type === this.anchor && this.anchorKey === null) {
        this.anchorKey = key;
      }
    }
  }

  get state(): T | null {
    if (this.anchorKey === null) return null;
    return this.rebuild(this.anchorKey) as T | null;
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
