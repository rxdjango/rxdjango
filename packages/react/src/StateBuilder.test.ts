import { describe, expect, it } from "vitest";

import { StateBuilder, type Model } from "./StateBuilder";

const model: Model = {
  "app.UserSerializer": { company: "app.CompanySerializer" },
  "app.CompanySerializer": {},
};

describe("StateBuilder", () => {
  it("returns null before any update", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    expect(builder.state).toBeNull();
  });

  it("rebuilds a nested instance from flat layers", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: 10 },
      { _type: "app.CompanySerializer", id: 10, name: "ACME" },
    ]);
    expect(builder.state).toEqual({
      id: 1,
      name: "Alice",
      _loaded: true,
      company: { id: 10, name: "ACME", _loaded: true },
    });
  });

  it("strips underscore-prefixed source keys but injects _loaded", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: null },
    ]);
    const keys = Object.keys(builder.state as object);
    expect(keys).not.toContain("_type");
    expect(keys).toContain("_loaded");
    expect((builder.state as { _loaded: boolean })._loaded).toBe(true);
  });

  it("keeps null relations null", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: null },
    ]);
    expect(builder.state).toEqual({
      id: 1,
      name: "Alice",
      _loaded: true,
      company: null,
    });
  });

  it("resolves missing children to an unloaded stub, not null", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: 99 },
    ]);
    expect(builder.state).toEqual({
      id: 1,
      name: "Alice",
      _loaded: true,
      company: { id: 99, _loaded: false },
    });
  });

  it("rebuilds array relations in order", () => {
    const listModel: Model = {
      "app.TeamSerializer": { members: "app.UserSerializer" },
      "app.UserSerializer": {},
    };
    const builder = new StateBuilder(listModel, "app.TeamSerializer");
    builder.update([
      { _type: "app.TeamSerializer", id: 1, members: [2, 1] },
      { _type: "app.UserSerializer", id: 1, name: "Alice" },
      { _type: "app.UserSerializer", id: 2, name: "Bob" },
    ]);
    expect(builder.state).toEqual({
      id: 1,
      _loaded: true,
      members: [
        { id: 2, name: "Bob", _loaded: true },
        { id: 1, name: "Alice", _loaded: true },
      ],
    });
  });

  it("applies later updates to existing instances", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: 10 },
      { _type: "app.CompanySerializer", id: 10, name: "ACME" },
    ]);
    builder.update([
      { _type: "app.CompanySerializer", id: 10, name: "ACME Corp" },
    ]);
    expect(builder.state).toEqual({
      id: 1,
      name: "Alice",
      _loaded: true,
      company: { id: 10, name: "ACME Corp", _loaded: true },
    });
  });
});

// Ported from the hand-written v0 suite
// (rxdjango-0/rxdjango-react/src/StateBuilder.test.ts). These pin the
// referential-identity contract React rendering depends on: an update
// produces new object references along the changed path only, instances
// shared between relations are the same object, and deletes drop the
// instance from parent arrays.

interface UserState {
  id: number;
  username?: string;
}

interface TaskState {
  id: number;
  taskName?: string;
  user?: UserState | null;
}

interface CustomerState {
  id: number;
  customerName?: string;
  tasks?: (TaskState | null)[];
}

interface ProjectState {
  id: number;
  projectName?: string;
  customer?: CustomerState | null;
  tasks?: (TaskState | null)[];
}

const projectModel: Model = {
  "project.ProjectSerializer": {
    customer: "project.CustomerSerializer",
    tasks: "project.TaskSerializer",
  },
  "project.CustomerSerializer": { tasks: "project.TaskSerializer" },
  "project.TaskSerializer": { user: "project.UserSerializer" },
  "project.UserSerializer": {},
};

const project = (fields: object) => ({
  _type: "project.ProjectSerializer",
  id: 1,
  ...fields,
});

const customer = (id: number, fields: object) => ({
  _type: "project.CustomerSerializer",
  id,
  ...fields,
});

const task = (id: number, fields: object) => ({
  _type: "project.TaskSerializer",
  id,
  ...fields,
});

const user = (id: number, fields: object) => ({
  _type: "project.UserSerializer",
  id,
  ...fields,
});

function projectBuilder() {
  return new StateBuilder<ProjectState>(
    projectModel,
    "project.ProjectSerializer",
  );
}

describe("StateBuilder identity semantics (ported from v0)", () => {
  it("returns the same state reference while nothing changes", () => {
    const builder = projectBuilder();
    builder.update([project({ projectName: "Project #1", tasks: [] })]);
    expect(builder.state).toBe(builder.state);
  });

  it("changes the object reference when an instance is updated", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1] }),
      task(1, { taskName: "Task #1" }),
    ]);
    const before = builder.state!.tasks![0];

    builder.update([task(1, { taskName: "changed" })]);
    const after = builder.state!.tasks![0];

    expect(after).not.toBe(before);
    expect(after!.taskName).toBe("changed");
  });

  it("changes every ancestor reference when a nested child updates", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", customer: 2 }),
      customer(2, { customerName: "Customer #2", tasks: [1] }),
      task(1, { taskName: "Task #1", user: 1 }),
      user(1, { username: "User #1" }),
    ]);
    const before = builder.state!;

    builder.update([user(1, { username: "renamed" })]);
    const after = builder.state!;

    expect(after).not.toBe(before);
    expect(after.customer).not.toBe(before.customer);
    expect(after.customer!.tasks).not.toBe(before.customer!.tasks);
    expect(after.customer!.tasks![0]).not.toBe(before.customer!.tasks![0]);
    expect(after.customer!.tasks![0]!.user!.username).toBe("renamed");
  });

  it("keeps the references of untouched siblings", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", customer: 2, tasks: [1, 2] }),
      customer(2, { customerName: "Customer #2", tasks: [] }),
      task(1, { taskName: "Task #1" }),
      task(2, { taskName: "Task #2" }),
    ]);
    const before = builder.state!;

    builder.update([task(1, { taskName: "changed" })]);
    const after = builder.state!;

    expect(after).not.toBe(before);
    expect(after.tasks).not.toBe(before.tasks);
    expect(after.tasks![0]).not.toBe(before.tasks![0]);
    expect(after.tasks![1]).toBe(before.tasks![1]);
    expect(after.customer).toBe(before.customer);
  });

  it("shares the reference of an instance appearing in two relations, child arriving last", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", customer: 1, tasks: [1, 2, 3] }),
      customer(1, { customerName: "Customer #1", tasks: [3, 4, 5] }),
      task(3, { taskName: "Task #3" }),
    ]);
    const state = builder.state!;
    expect(state.tasks![2]).not.toBeNull();
    expect(state.tasks![2]).toBe(state.customer!.tasks![0]);
  });

  it("shares the reference of an instance appearing in two relations, child arriving early", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", customer: 1, tasks: [1, 2, 3] }),
      task(3, { taskName: "Task #3" }),
      customer(1, { customerName: "Customer #1", tasks: [3, 4, 5] }),
    ]);
    const state = builder.state!;
    expect(state.tasks![2]).not.toBeNull();
    expect(state.tasks![2]).toBe(state.customer!.tasks![0]);
  });

  it("resolves children delivered before their parent in the same payload", () => {
    const builder = projectBuilder();
    builder.update([
      task(1, { taskName: "Task #1" }),
      project({ projectName: "Project #1", tasks: [1] }),
    ]);
    expect(builder.state!.tasks![0]).toEqual({
      id: 1,
      taskName: "Task #1",
      _loaded: true,
    });
  });

  it("initializes empty relation lists as empty arrays", () => {
    const builder = projectBuilder();
    builder.update([project({ projectName: "Project #1", tasks: [] })]);
    expect(builder.state!.tasks).toEqual([]);
  });

  it("removes a deleted instance from parent arrays", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1, 2, 3] }),
      task(1, { taskName: "Task #1" }),
      task(2, { taskName: "Task #2" }),
      task(3, { taskName: "Task #3" }),
    ]);

    builder.update([{ _type: "project.TaskSerializer", _del: 2 }]);
    const state = builder.state!;

    expect(state.tasks!.length).toBe(2);
    expect(state.tasks![0]!.id).toBe(1);
    expect(state.tasks![1]!.id).toBe(3);
  });
});

// Ported from ADR-0014. The server subscribes to the event stream before
// fetching the initial snapshot, so a snapshot layer can arrive after a
// newer event for the same row. Layers from reactive models carry a `_v`
// version and reconcile by watermark, not arrival order; deletes leave a
// tombstone; versionless layers (non-reactive models) are always applied.

describe("StateBuilder version watermarks (ADR-0014)", () => {
  it("applies a layer with a higher version", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1] }),
      task(1, { taskName: "old", _v: 1 }),
    ]);
    builder.update([task(1, { taskName: "new", _v: 2 })]);
    expect(builder.state!.tasks![0]!.taskName).toBe("new");
  });

  it("discards a snapshot layer older than an applied event", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1] }),
      task(1, { taskName: "live event", _v: 2 }),
    ]);
    builder.update([task(1, { taskName: "stale snapshot", _v: 1 })]);
    expect(builder.state!.tasks![0]!.taskName).toBe("live event");
  });

  it("discards a layer carrying an already-applied version", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1] }),
      task(1, { taskName: "first delivery", _v: 2 }),
    ]);
    builder.update([task(1, { taskName: "re-delivery", _v: 2 })]);
    expect(builder.state!.tasks![0]!.taskName).toBe("first delivery");
  });

  it("keeps every reference untouched when a stale layer is discarded", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", customer: 2, tasks: [1] }),
      customer(2, { customerName: "Customer #2", tasks: [1] }),
      task(1, { taskName: "Task #1", _v: 2 }),
    ]);
    const before = builder.state!;

    builder.update([task(1, { taskName: "stale", _v: 1 })]);

    expect(builder.state).toBe(before);
  });

  it("reconciles an event delivered before the snapshot of the same row", () => {
    const builder = projectBuilder();
    builder.update([task(1, { taskName: "live event", _v: 2 })]);
    builder.update([
      project({ projectName: "Project #1", tasks: [1] }),
      task(1, { taskName: "stale snapshot", _v: 1 }),
    ]);
    expect(builder.state!.tasks![0]!.taskName).toBe("live event");
  });

  it("does not let a stale snapshot resurrect a deleted row", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1, 2] }),
      task(1, { taskName: "Task #1", _v: 1 }),
      task(2, { taskName: "Task #2", _v: 1 }),
    ]);
    builder.update([{ _type: "project.TaskSerializer", _del: 2, _v: 2 }]);

    builder.update([task(2, { taskName: "Task #2", _v: 1 })]);
    expect(builder.state!.tasks!.length).toBe(1);

    // Even when a later parent layer lists the pk again, the tombstone has
    // kept the stale row out of the index -- the slot renders as an unloaded
    // stub (index-miss is index-miss, whether "not yet arrived" or
    // "deleted and not resurrected"), not as the deleted row's data.
    builder.update([project({ projectName: "Project #1", tasks: [1, 2] })]);
    expect(builder.state!.tasks![1]).toEqual({ id: 2, _loaded: false });
  });

  it("discards a delete older than the applied row", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1] }),
      task(1, { taskName: "fresh", _v: 3 }),
    ]);
    builder.update([{ _type: "project.TaskSerializer", _del: 1, _v: 2 }]);

    expect(builder.state!.tasks!.length).toBe(1);
    expect(builder.state!.tasks![0]!.taskName).toBe("fresh");
  });

  it("always applies versionless layers", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1] }),
      task(1, { taskName: "first" }),
    ]);
    builder.update([task(1, { taskName: "second" })]);
    expect(builder.state!.tasks![0]!.taskName).toBe("second");
  });
});

// Ported from the hand-written v0 suite
// (rxdjango-0/rxdjango-react/src/StateBuilder.test.ts). v0 pinned unloaded
// placeholders as first-class partial state; ADR-0016 restores that
// semantic on top of the rebuild's identity/watermark machinery (design D4).

describe("StateBuilder stub materialization (design D4, ported from v0)", () => {
  it("materializes stubs for array relation members that haven't arrived", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1, 2, 3] }),
      task(1, { taskName: "Task #1" }),
    ]);
    expect(builder.state!.tasks).toEqual([
      { id: 1, taskName: "Task #1", _loaded: true },
      { id: 2, _loaded: false },
      { id: 3, _loaded: false },
    ]);
  });

  it("loads a set member when its data is received, leaving siblings unloaded", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1, 2] }),
    ]);
    builder.update([task(1, { taskName: "Task #1" })]);

    const state = builder.state!;
    expect(state.tasks![0]).toEqual({ id: 1, taskName: "Task #1", _loaded: true });
    expect(state.tasks![1]).toEqual({ id: 2, _loaded: false });
  });

  it("materializes a stub for a scalar (FK) relation that hasn't arrived", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1] }),
      task(1, { taskName: "Task #1", user: 7 }),
    ]);
    expect(builder.state!.tasks![0]!.user).toEqual({ id: 7, _loaded: false });
  });

  it("keeps a stub's reference stable across reads while unloaded", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1, 2] }),
      task(1, { taskName: "Task #1" }),
    ]);
    expect(builder.state!.tasks![1]).toBe(builder.state!.tasks![1]);
  });

  it("replaces a stub with the real instance on arrival, changing reference", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1, 2] }),
      task(1, { taskName: "Task #1" }),
    ]);
    const before = builder.state!.tasks![1];
    expect(before).toEqual({ id: 2, _loaded: false });

    builder.update([task(2, { taskName: "Task #2" })]);
    const after = builder.state!.tasks![1];

    expect(after).not.toBe(before);
    expect(after).toEqual({ id: 2, taskName: "Task #2", _loaded: true });
  });

  it("replaces a foreign-key stub when it arrives, changing reference", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1] }),
      task(1, { taskName: "Task #1", user: 7 }),
    ]);
    const before = builder.state!.tasks![0]!.user;

    builder.update([user(7, { username: "Grace" })]);
    const after = builder.state!.tasks![0]!.user;

    expect(after).not.toBe(before);
    expect(after).toEqual({ id: 7, username: "Grace", _loaded: true });
  });

  it("propagates a stub-to-real replacement up the ancestor chain", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", customer: 2 }),
      customer(2, { customerName: "Customer #2", tasks: [1] }),
      task(1, { taskName: "Task #1", user: 1 }),
      // `user` is never delivered: task.user stays a stub.
    ]);
    const before = builder.state!;
    expect(before.customer!.tasks![0]!.user).toEqual({ id: 1, _loaded: false });

    builder.update([user(1, { username: "renamed" })]);
    const after = builder.state!;

    expect(after).not.toBe(before);
    expect(after.customer).not.toBe(before.customer);
    expect(after.customer!.tasks).not.toBe(before.customer!.tasks);
    expect(after.customer!.tasks![0]).not.toBe(before.customer!.tasks![0]);
    expect(after.customer!.tasks![0]!.user).toEqual({
      id: 1,
      username: "renamed",
      _loaded: true,
    });
  });

  it("replaces a stub regardless of the arriving instance's version", () => {
    const builder = projectBuilder();
    builder.update([
      project({ projectName: "Project #1", tasks: [1, 2] }),
      task(1, { taskName: "Task #1", _v: 1 }),
    ]);
    expect(builder.state!.tasks![1]).toEqual({ id: 2, _loaded: false });

    // No watermark was ever recorded for task 2 (a stub carries no `_v`), so
    // any version -- including one that would look "stale" for an
    // already-seen key -- applies unconditionally.
    builder.update([task(2, { taskName: "Task #2", _v: 1 })]);
    expect(builder.state!.tasks![1]).toEqual({
      id: 2,
      taskName: "Task #2",
      _loaded: true,
    });
  });
});
