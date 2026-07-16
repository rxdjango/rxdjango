import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PersistentSocket } from "./PersistentSocket";

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
    for (const listener of this.listeners["open"] ?? []) listener({});
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
    for (const listener of this.listeners["close"] ?? []) listener({});
  }

  message(data: string): void {
    for (const listener of this.listeners["message"] ?? []) listener({ data });
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  FakeWebSocket.instances = [];
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("PersistentSocket: backoff (task 4.1)", () => {
  it("reconnects with exponential backoff on an unexpected close", () => {
    const socket = new PersistentSocket("ws://backend/ws/", {
      initialReconnectInterval: 100,
      maxReconnectInterval: 1000,
    });
    socket.connect();
    expect(FakeWebSocket.instances).toHaveLength(1);

    FakeWebSocket.instances[0]!.close();
    expect(FakeWebSocket.instances).toHaveLength(1); // no immediate reconnect

    vi.advanceTimersByTime(99);
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    // Second failure waits double the first interval (200ms).
    FakeWebSocket.instances[1]!.close();
    vi.advanceTimersByTime(199);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);
  });

  it("caps the backoff delay at the configured maximum", () => {
    const socket = new PersistentSocket("ws://backend/ws/", {
      initialReconnectInterval: 100,
      maxReconnectInterval: 250,
    });
    socket.connect();

    // 100 -> 200 -> capped at 250 (not 400).
    FakeWebSocket.instances[0]!.close();
    vi.advanceTimersByTime(100);
    expect(FakeWebSocket.instances).toHaveLength(2);

    FakeWebSocket.instances[1]!.close();
    vi.advanceTimersByTime(200);
    expect(FakeWebSocket.instances).toHaveLength(3);

    FakeWebSocket.instances[2]!.close();
    vi.advanceTimersByTime(249);
    expect(FakeWebSocket.instances).toHaveLength(3);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(4);
  });

  it("resets the backoff delay after a successful open", () => {
    const socket = new PersistentSocket("ws://backend/ws/", {
      initialReconnectInterval: 100,
      maxReconnectInterval: 10000,
    });
    socket.connect();

    FakeWebSocket.instances[0]!.close();
    vi.advanceTimersByTime(100);
    expect(FakeWebSocket.instances).toHaveLength(2);

    // The second connection succeeds -- backoff resets to the initial delay.
    FakeWebSocket.instances[1]!.open();
    FakeWebSocket.instances[1]!.close();
    vi.advanceTimersByTime(99);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);
  });

  it("calls onOpen and onMessage", () => {
    const socket = new PersistentSocket("ws://backend/ws/");
    const opens: number[] = [];
    const messages: string[] = [];
    socket.onOpen = () => opens.push(1);
    socket.onMessage = (data) => messages.push(data);
    socket.connect();

    FakeWebSocket.instances[0]!.open();
    FakeWebSocket.instances[0]!.message("hello");

    expect(opens).toEqual([1]);
    expect(messages).toEqual(["hello"]);
  });

  it("send() delivers only while open and reports whether it did", () => {
    const socket = new PersistentSocket("ws://backend/ws/");
    socket.connect();

    expect(socket.send("before-open")).toBe(false);

    FakeWebSocket.instances[0]!.open();
    expect(socket.send("after-open")).toBe(true);
    expect(FakeWebSocket.instances[0]!.sent).toEqual(["after-open"]);
  });
});

describe("PersistentSocket: stop() halts retrying (task 4.1)", () => {
  it("cancels a pending reconnect attempt and schedules no further ones", () => {
    const socket = new PersistentSocket("ws://backend/ws/", {
      initialReconnectInterval: 100,
    });
    socket.connect();
    FakeWebSocket.instances[0]!.close(); // schedules a reconnect in 100ms

    socket.stop();
    vi.advanceTimersByTime(10000);

    expect(FakeWebSocket.instances).toHaveLength(1); // no reconnect happened
  });

  it("does not close an already-open connection", () => {
    const socket = new PersistentSocket("ws://backend/ws/");
    socket.connect();
    FakeWebSocket.instances[0]!.open();

    socket.stop();

    expect(FakeWebSocket.instances[0]!.readyState).toBe(FakeWebSocket.OPEN);
  });

  it("a later close is not followed by any reconnect attempt once stopped", () => {
    const socket = new PersistentSocket("ws://backend/ws/", {
      initialReconnectInterval: 100,
    });
    socket.connect();
    FakeWebSocket.instances[0]!.open();
    socket.stop();

    FakeWebSocket.instances[0]!.close();
    vi.advanceTimersByTime(10000);

    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("resume() re-arms retrying and reconnects immediately if currently down", () => {
    const socket = new PersistentSocket("ws://backend/ws/", {
      initialReconnectInterval: 100,
    });
    socket.connect();
    FakeWebSocket.instances[0]!.close();
    socket.stop(); // cancels the pending reconnect timer

    vi.advanceTimersByTime(10000);
    expect(FakeWebSocket.instances).toHaveLength(1);

    socket.resume();
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("resume() while still connected does not open a second socket", () => {
    const socket = new PersistentSocket("ws://backend/ws/");
    socket.connect();
    FakeWebSocket.instances[0]!.open();
    socket.stop();

    socket.resume();

    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});
