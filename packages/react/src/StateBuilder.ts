/**
 * Rebuilds a nested instance from the flat layers sent by the backend.
 *
 * The Python ``StateModel`` flattens a nested ``ModelSerializer`` into a
 * list of dicts, each tagged with ``_type``. ``StateBuilder`` keeps the
 * latest flat copy of each instance keyed by ``_type:id`` and follows the
 * relation map produced at compile time to splice them back into the
 * nested shape declared by the serializer tree.
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

interface FlatInstance {
  _type: string;
  id?: number;
  _v?: number;
  _del?: number;
  [key: string]: unknown;
}

export class StateBuilder<T> {
  private model: Model;
  private anchor: string;
  private index: Record<string, FlatInstance> = {};
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
        // Tombstone: drop the row but keep its watermark so a stale snapshot
        // arriving afterwards is discarded by the version check above.
        delete this.index[key];
        continue;
      }

      this.index[key] = instance;
      if (instance._type === this.anchor && this.anchorKey === null) {
        this.anchorKey = key;
      }
    }
  }

  get state(): T | null {
    if (this.anchorKey === null) return null;
    const root = this.index[this.anchorKey];
    if (root === undefined) return null;
    return this.rebuild(root) as T;
  }

  private rebuild(instance: FlatInstance): Record<string, unknown> {
    const relations = this.model[instance._type] ?? {};
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(instance)) {
      if (key.startsWith("_")) continue;
      const childType = relations[key];
      if (childType === undefined) {
        out[key] = value;
        continue;
      }
      if (Array.isArray(value)) {
        out[key] = value.map((id) => this.resolveChild(childType, id as number));
      } else if (value === null || value === undefined) {
        out[key] = null;
      } else {
        out[key] = this.resolveChild(childType, value as number);
      }
    }
    return out;
  }

  private resolveChild(type: string, id: number): Record<string, unknown> | null {
    const child = this.index[`${type}:${id}`];
    if (child === undefined) return null;
    return this.rebuild(child);
  }
}

export default StateBuilder;
