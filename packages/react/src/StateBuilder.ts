/**
 * Rebuilds a nested instance from the flat layers sent by the backend.
 *
 * The Python ``StateModel`` flattens a nested ``ModelSerializer`` into a
 * list of dicts, each tagged with ``_type``. ``StateBuilder`` keeps the
 * latest flat copy of each instance keyed by ``_type:id`` and follows the
 * relation map produced at compile time to splice them back into the
 * nested shape declared by the serializer tree.
 */

export type RelationMap = Record<string, string>;
export type Model = Record<string, RelationMap>;

interface FlatInstance {
  _type: string;
  id?: number;
  [key: string]: unknown;
}

export class StateBuilder<T> {
  private model: Model;
  private anchor: string;
  private index: Record<string, FlatInstance> = {};
  private anchorKey: string | null = null;

  constructor(model: Model, anchor: string) {
    this.model = model;
    this.anchor = anchor;
  }

  update(instances: FlatInstance[]): void {
    for (const instance of instances) {
      const id = instance.id;
      const key = id === undefined ? instance._type : `${instance._type}:${id}`;
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
