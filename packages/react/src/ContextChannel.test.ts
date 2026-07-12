import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ContextChannel } from "./ContextChannel";

type Listener = (ev: { data?: string }) => void;

class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
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
      company: { id: 10, name: "ACME" },
    });
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
