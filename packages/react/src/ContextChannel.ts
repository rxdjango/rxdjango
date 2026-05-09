/**
 * Reactive surface exposed by every ContextChannel.
 *
 * `subscribe` and `getVersion` are bound to the channel instance so their
 * identity is stable across renders — required by `useSyncExternalStore`.
 * `getVersion` returns a monotonically increasing integer; React diffs it
 * with `Object.is` to decide whether to re-render.
 */
export interface ChannelRx {
  subscribe: (listener: () => void) => () => void;
  getVersion: () => number;
  /**
   * RPC entry point used by generated action wrappers. The makefrontend
   * code emitter produces `this.rx.callAction('methodName', [arg1, arg2])`
   * for every `@action` on the Django channel.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  callAction: (action: string, params: any[]) => Promise<any>;
}

/**
 * Base class for generated TypeScript channel classes.
 *
 * Subclasses are emitted by `makefrontend` and bind a Django ContextChannel
 * to a typed React surface. State (e.g. `channel.counter`) is exposed
 * directly on the instance; the `rx` object carries the React subscription
 * plumbing.
 *
 * @template T - The type of the root/anchor state object.
 */
export abstract class ContextChannel<T = unknown> {
  declare protected readonly _state?: T;

  private _version = 0;
  private readonly _listeners = new Set<() => void>();

  readonly rx: ChannelRx = {
    subscribe: (listener: () => void) => {
      this._listeners.add(listener);
      return () => {
        this._listeners.delete(listener);
      };
    },
    getVersion: () => this._version,
    callAction: (action, params) => this._callAction(action, params),
  };

  /**
   * Dispatch an action to the Django channel over the WebSocket.
   * Stub for now — wired up alongside the connection layer.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  protected async _callAction(_action: string, _params: any[]): Promise<any> {
    throw new Error("ContextChannel._callAction not implemented");
  }

  /**
   * Mark the channel state as updated and notify React subscribers.
   * Generated subclasses / StateBuilder call this after applying a diff.
   */
  protected notify(): void {
    this._version++;
    this._listeners.forEach((listener) => listener());
  }
}

export default ContextChannel;
