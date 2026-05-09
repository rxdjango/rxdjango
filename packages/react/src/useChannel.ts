import { useState, useSyncExternalStore } from "react";
import type { ContextChannel } from "./ContextChannel";

export type ContextChannelClass<C extends ContextChannel> = new (
  ...args: never[]
) => C;

/**
 * React hook that returns a stable ContextChannel instance and re-renders
 * the component whenever the channel publishes a new state.
 *
 * Components read state directly off the channel (e.g. `channel.counter`);
 * the hook's only job is to wire the channel's `rx` reactive surface into
 * React's `useSyncExternalStore`.
 */
export function useChannel<C extends ContextChannel>(
  ChannelClass: ContextChannelClass<C>,
): C {
  const [channel] = useState(() => new ChannelClass());
  useSyncExternalStore(channel.rx.subscribe, channel.rx.getVersion);
  return channel;
}

export default useChannel;
