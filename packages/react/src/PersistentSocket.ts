/**
 * A persistent WebSocket transport: reconnects automatically with
 * exponential backoff on an unexpected close, resets the backoff after a
 * successful open, and stops retrying once `stop()` is called (design D5,
 * react-client "Persistent socket with backoff").
 *
 * Ported from v0's `PersistentWebSocket`
 * (`rxdjango-0/rxdjango-react/src/PersistentWebsocket.ts`): the backoff
 * schedule (double on each retry, capped, reset on open) and the
 * stop-prevents-further-reconnects behavior are carried over; the
 * auth-handshake/`lastUpdate` machinery is not -- this rebuild has no
 * server-side session to resume (ADR-0019 D5: a reconnect is a rebind over
 * a warm client index, not a replay).
 */
export interface PersistentSocketOptions {
  /** Initial reconnect delay in ms; doubles on each consecutive failure. */
  initialReconnectInterval?: number;
  /** Upper bound the backoff delay is capped at. */
  maxReconnectInterval?: number;
}

export class PersistentSocket {
  onOpen: () => void = () => {};
  onMessage: (data: string) => void = () => {};
  onClose: () => void = () => {};

  private readonly url: string;
  private readonly initialReconnectInterval: number;
  private readonly maxReconnectInterval: number;
  private reconnectInterval: number;
  private ws?: WebSocket;
  private timer?: ReturnType<typeof setTimeout>;
  private stopped = false;

  constructor(url: string, options: PersistentSocketOptions = {}) {
    this.url = url;
    this.initialReconnectInterval = options.initialReconnectInterval ?? 250;
    this.maxReconnectInterval = options.maxReconnectInterval ?? 10000;
    this.reconnectInterval = this.initialReconnectInterval;
  }

  /** Open a connection. A no-op if already connected/connecting. Does not
   * itself consult `stop()`'s flag -- `resume()` is what re-arms retrying
   * and calls this; a bare `connect()` after `stop()` (e.g. the very first
   * connection) is expected to proceed. */
  connect(): void {
    if (this.ws !== undefined) return;

    const ws = new WebSocket(this.url);
    this.ws = ws;

    ws.addEventListener('open', () => {
      // Reset on open (design D5): a healthy connection forgives past
      // failures, so the *next* drop starts backoff from the initial delay.
      this.reconnectInterval = this.initialReconnectInterval;
      this.onOpen();
    });

    ws.addEventListener('message', (ev: MessageEvent) => {
      const data = typeof ev.data === 'string' ? ev.data : String(ev.data);
      this.onMessage(data);
    });

    ws.addEventListener('close', () => {
      this.ws = undefined;
      this.onClose();
      if (this.stopped) return;
      this.timer = setTimeout(() => this.connect(), this.reconnectInterval);
      this.reconnectInterval = Math.min(
        this.reconnectInterval * 2,
        this.maxReconnectInterval,
      );
    });
  }

  /** `true` once the underlying socket has completed its open handshake. */
  get isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /** Send a frame if open; returns whether it was sent immediately. */
  send(data: string): boolean {
    if (this.isOpen) {
      this.ws!.send(data);
      return true;
    }
    return false;
  }

  /**
   * Stop retrying (react-client: "Unmounting ... SHALL stop reconnection").
   * Cancels any pending backoff timer so no further connection attempts are
   * made; an already-open connection is left alone (an unmount is not by
   * itself a reason to sever a healthy socket -- it only forgoes chasing
   * *future* drops). Idempotent; pair with `resume()` to re-arm.
   */
  stop(): void {
    this.stopped = true;
    if (this.timer !== undefined) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }
  }

  /**
   * Re-arm retrying after `stop()` (a remounting subscriber). If the
   * connection is currently down with no attempt pending, reconnects right
   * away rather than waiting on a backoff timer that was never scheduled.
   */
  resume(): void {
    this.stopped = false;
    if (this.ws === undefined && this.timer === undefined) {
      this.connect();
    }
  }
}

export default PersistentSocket;
