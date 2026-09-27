/**
 * Whether the demo asks for its login, and whether this browser has signed in, as the web server
 * says (`/bff/session`). Read once when the app starts, and updated on signing in and out.
 */

import { useSyncExternalStore } from "react";
import { session, type Session } from "./client";

const listeners = new Set<() => void>();
let current: Session | undefined;
let loading: Promise<void> | undefined;

function set(next: Session): void {
  current = next;
  listeners.forEach((listener) => listener());
}

/** Asks the web server again; a failure leaves the state unknown rather than guessing it. */
export function refreshSession(): Promise<void> {
  loading = session()
    .then(set)
    .catch(() => undefined);
  return loading;
}

export function markSignedIn(signedIn: boolean): void {
  set({ login_required: current?.login_required ?? true, signed_in: signedIn });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (!current && !loading) void refreshSession();
  return () => listeners.delete(listener);
}

/** Undefined until the web server has answered. */
export function useSession(): Session | undefined {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => current,
  );
}

/** For the tests: every test starts before the web server has been asked. */
export function forgetSession(): void {
  current = undefined;
  loading = undefined;
}
