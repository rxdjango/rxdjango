import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ContextChannel } from "./ContextChannel";

type Listener = (ev: { data?: string }) => void;

class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readyState = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  private listeners: Record<string, Listener[]> = {};

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: Listener): void {
    (this.listeners[type] ??= []).push(listener);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    for (const listener of this.listeners["open"] ?? []) {
      listener({});
    }
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
    for (const listener of this.listeners["close"] ?? []) {
      listener({});
    }
  }

  message(frame: object): void {
    const data = JSON.stringify(frame);
    for (const listener of this.listeners["message"] ?? []) {
      listener({ data });
    }
  }
}

// _onMessage defers each frame to a macrotask; flush them.
const tick = () =>
  new Promise((resolve) => {
    setTimeout(resolve, 0);
  });

class TestChannel extends ContextChannel<unknown> {
  declare counter?: number;
  declare user?: unknown;
  declare tasks?: unknown;

  protected override endpoint = "/ws/test/";
  protected override baseURL = "ws://backend";

  protected override _modelFields = {
    user: {
      anchor: "app.UserSerializer",
      model: {
        "app.UserSerializer": { company: "app.CompanySerializer" },
        "app.CompanySerializer": {},
      },
    },
    tasks: {
      anchor: "app.TaskSerializer",
      model: { "app.TaskSerializer": {} },
      many: true,
    },
  };
}

function subscribedChannel() {
  const channel = new TestChannel();
  const listener = vi.fn();
  channel.rx.subscribe(listener);
  const ws = FakeWebSocket.instances.at(-1)!;
  return { channel, listener, ws };
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  FakeWebSocket.instances = [];
  vi.unstubAllGlobals();
});

describe("ContextChannel", () => {
  it("connects lazily on first subscription", () => {
    const channel = new TestChannel();
    expect(FakeWebSocket.instances).toHaveLength(0);
    channel.rx.subscribe(() => {});
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0]!.url).toBe("ws://backend/ws/test/");
  });

  it("notifies subscribers and bumps version on ready", async () => {
    const { channel, listener, ws } = subscribedChannel();
    const before = channel.rx.getVersion();
    ws.message({ t: "ready", protocol: "0.1.0" });
    await tick();
    expect(listener).toHaveBeenCalledTimes(1);
    expect(channel.rx.getVersion()).toBe(before + 1);
  });

  it("applies scalar rx frames to the instance", async () => {
    const { channel, ws } = subscribedChannel();
    ws.message({ t: "rx", f: "counter", v: 41 });
    await tick();
    expect(channel.counter).toBe(41);
  });

  it("rebuilds model fields from flat payloads", async () => {
    const { channel, ws } = subscribedChannel();
    ws.message({
      t: "rx",
      f: "user",
      v: [
        { _type: "app.UserSerializer", id: 1, name: "Alice", company: 10 },
        { _type: "app.CompanySerializer", id: 10, name: "ACME" },
      ],
    });
    await tick();
    expect(channel.user).toEqual({
      id: 1,
      name: "Alice",
      _loaded: true,
      company: { id: 10, name: "ACME", _loaded: true },
    });
  });

  it("derives a many=True field's state from the q bind descriptor", async () => {
    const { channel, ws } = subscribedChannel();

    // Before the first snapshot: null, not [].
    expect(channel.tasks).toBeUndefined();

    ws.message({
      t: "rx",
      f: "tasks",
      v: [
        { _type: "app.TaskSerializer", id: 1, status: "open", priority: 1 },
        { _type: "app.TaskSerializer", id: 2, status: "open", priority: 5 },
      ],
      q: { w: [["status", "exact", "open"]], s: ["-priority"] },
    });
    await tick();

    expect(channel.tasks).toEqual([
      { id: 2, status: "open", priority: 5, _loaded: true },
      { id: 1, status: "open", priority: 1, _loaded: true },
    ]);

    // An ordinary update frame (no q) flips a member out via the residual.
    ws.message({
      t: "rx",
      f: "tasks",
      v: [{ _type: "app.TaskSerializer", id: 2, status: "closed", priority: 5 }],
    });
    await tick();

    expect(channel.tasks).toEqual([
      { id: 1, status: "open", priority: 1, _loaded: true },
    ]);

    // A rebind (fresh q frame) demotes row 1, replacing the array with [].
    ws.message({
      t: "rx",
      f: "tasks",
      v: [],
      q: { w: [["status", "exact", "open"]], s: ["-priority"] },
    });
    await tick();

    expect(channel.tasks).toEqual([]);
  });

  it("nulls a model field when the backend sends null", async () => {
    const { channel, ws } = subscribedChannel();
    ws.message({
      t: "rx",
      f: "user",
      v: [{ _type: "app.UserSerializer", id: 1, name: "Alice", company: null }],
    });
    await tick();
    ws.message({ t: "rx", f: "user", v: null });
    await tick();
    expect(channel.user).toBeNull();
  });

  it("applies streamed insert ops, growing the array in order", async () => {
    const { channel, ws } = subscribedChannel();
    ws.message({ t: "rx", f: "counter", v: [] });
    await tick();
    const first = channel.counter as unknown as number[];

    ws.message({ t: "rx", f: "counter", o: "i", v: [0, 1] });
    await tick();
    const second = channel.counter as unknown as number[];
    expect(second).toEqual([1]);
    expect(second).not.toBe(first);

    ws.message({ t: "rx", f: "counter", o: "i", v: [1, 2] });
    await tick();
    ws.message({ t: "rx", f: "counter", o: "i", v: [2, 3] });
    await tick();

    expect(channel.counter).toEqual([1, 2, 3]);
  });

  it("converges a mixed insert/set/delete burst to the server's list", async () => {
    const { channel, ws } = subscribedChannel();
    ws.message({ t: "rx", f: "counter", v: [1, 2, 3] });
    await tick();

    ws.message({ t: "rx", f: "counter", o: "i", v: [3, 4] });
    await tick();
    ws.message({ t: "rx", f: "counter", o: "i", v: [0, -1] });
    await tick();
    ws.message({ t: "rx", f: "counter", o: "s", v: [1, 99] });
    await tick();
    ws.message({ t: "rx", f: "counter", o: "d", v: 4 });
    await tick();

    expect(channel.counter).toEqual([-1, 99, 2, 3]);
  });

  it("replace after ops resets the array to exactly the frame's value", async () => {
    const { channel, ws } = subscribedChannel();
    ws.message({ t: "rx", f: "counter", v: [1, 2, 3] });
    await tick();
    ws.message({ t: "rx", f: "counter", o: "i", v: [3, 4] });
    await tick();
    expect(channel.counter).toEqual([1, 2, 3, 4]);

    ws.message({ t: "rx", f: "counter", v: [9, 8] });
    await tick();

    expect(channel.counter).toEqual([9, 8]);
  });

  it("discards an o frame for a field whose current value isn't an array", async () => {
    const { channel, ws } = subscribedChannel();
    ws.message({ t: "rx", f: "counter", v: 41 });
    await tick();

    ws.message({ t: "rx", f: "counter", o: "i", v: [0, 1] });
    await tick();

    expect(channel.counter).toBe(41);
  });

  it("resolves actions with the response payload", async () => {
    const { channel, ws } = subscribedChannel();
    ws.open();
    const promise = channel.rx.callAction("ping", []);
    expect(JSON.parse(ws.sent[0]!)).toEqual({
      t: "ac",
      a: "ping",
      id: "1",
      p: [],
    });
    ws.message({ t: "ac", id: "1", r: "pong", e: 0 });
    await tick();
    await expect(promise).resolves.toBe("pong");
  });

  it("rejects actions on error frames with the code", async () => {
    const { channel, ws } = subscribedChannel();
    ws.open();
    const promise = channel.rx.callAction("boom", []);
    // Attach the expectation before the frame lands so the rejection is
    // never observed as unhandled between macrotasks.
    const expectation = expect(promise).rejects.toMatchObject({
      message: "Forbidden",
      code: 403,
    });
    ws.message({ t: "ac", id: "1", e: [403, "Forbidden"] });
    await expectation;
  });

  it("queues actions sent before the socket opens", async () => {
    const { channel, ws } = subscribedChannel();
    const promise = channel.rx.callAction("ping", []);
    expect(ws.sent).toHaveLength(0);
    ws.open();
    expect(ws.sent).toHaveLength(1);
    ws.message({ t: "ac", id: "1", r: "pong", e: 0 });
    await tick();
    await expect(promise).resolves.toBe("pong");
  });

  it("throws when calling an action with no connection", async () => {
    const channel = new TestChannel();
    await expect(channel.rx.callAction("ping", [])).rejects.toThrow(
      /no websocket connection/,
    );
  });

  it("stops notifying after unsubscribe", async () => {
    const { listener, ws, channel } = subscribedChannel();
    const unsubscribe = channel.rx.subscribe(listener);
    unsubscribe();
    ws.message({ t: "ready", protocol: "0.1.0" });
    await tick();
    expect(listener).not.toHaveBeenCalled();
  });
});

// Persistent socket integration (react-client "Persistent socket with
// backoff" / "Reconnect is a rebind over a warm index", static-queryset-lists
// tasks 4.1/4.2). Uses fake timers locally since these tests drive the
// backoff schedule directly, unlike the macrotask-only tests above.

describe("ContextChannel: persistent socket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const flush = () => vi.advanceTimersByTimeAsync(0);

  it("heals a dropped connection with backoff and keeps notifying without remounting", async () => {
    const channel = new TestChannel();
    const listener = vi.fn();
    channel.rx.subscribe(listener);
    const first = FakeWebSocket.instances[0]!;
    first.open();

    first.close();
    expect(FakeWebSocket.instances).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(10000);
    expect(FakeWebSocket.instances.length).toBeGreaterThan(1);

    const second = FakeWebSocket.instances.at(-1)!;
    second.open();
    second.message({ t: "ready", protocol: "0.3.0" });
    await flush();

    expect(listener).toHaveBeenCalled();
  });

  it("stops attempting to reconnect once the last subscriber unmounts", async () => {
    const channel = new TestChannel();
    const listener = vi.fn();
    const unsubscribe = channel.rx.subscribe(listener);
    const first = FakeWebSocket.instances[0]!;
    first.open();
    first.close(); // schedules a reconnect attempt

    unsubscribe();
    await vi.advanceTimersByTimeAsync(60000);

    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("reconnect is a rebind: a warm snapshot converges and keeps unchanged references", async () => {
    const channel = new TestChannel();
    channel.rx.subscribe(() => {});
    const first = FakeWebSocket.instances[0]!;
    first.open();

    first.message({
      t: "rx",
      f: "tasks",
      v: [
        { _type: "app.TaskSerializer", id: 1, status: "open", priority: 1, _v: 1 },
        { _type: "app.TaskSerializer", id: 2, status: "open", priority: 2, _v: 1 },
      ],
      q: { w: [["status", "exact", "open"]], s: ["id"] },
    });
    await flush();
    const beforeTasks = channel.tasks as unknown[];
    const beforeFirst = beforeTasks[0];

    // Connection drops and reconnects.
    first.close();
    await vi.advanceTimersByTimeAsync(10000);
    const second = FakeWebSocket.instances.at(-1)!;
    second.open();
    second.message({ t: "ready", protocol: "0.3.0" });
    await flush();

    // The new connection re-sends the same snapshot (idempotent under _v):
    // unchanged rows keep their references, and the derived list matches.
    second.message({
      t: "rx",
      f: "tasks",
      v: [
        { _type: "app.TaskSerializer", id: 1, status: "open", priority: 1, _v: 1 },
        { _type: "app.TaskSerializer", id: 2, status: "open", priority: 2, _v: 1 },
      ],
      q: { w: [["status", "exact", "open"]], s: ["id"] },
    });
    await flush();

    expect(channel.tasks).toEqual(beforeTasks);
    expect((channel.tasks as unknown[])[0]).toBe(beforeFirst);
  });
});
