/**
 * The landlord's own listings, kept in the browser (`localStorage`, under `umbral-my-listings`).
 *
 * The demo has no marketplace database: a real marketplace would keep these in its own, next to the
 * catalogue. What the AI service keeps is only what it needs to pause a review (its checkpointer), so
 * the listing and its status live here, and every page reads them through `useMyListings()`.
 *
 * A stored value that cannot be read, or a browser that refuses storage, starts an empty list instead
 * of breaking the page.
 */

import { useSyncExternalStore } from "react";
import type { ListingInput, ListingReview } from "../api/types";

const KEY = "umbral-my-listings";

export type MyListingStatus = "draft" | "changes_requested" | "pending_moderation" | "published";

export type MyListing = {
  id: string;
  input: ListingInput;
  status: MyListingStatus;
  // The last quick review, of the text as it was then. It says nothing about publishing.
  quickReview?: ListingReview;
  // ISO timestamp.
  updatedAt: string;
};

const STATUSES: MyListingStatus[] = ["draft", "changes_requested", "pending_moderation", "published"];

const listeners = new Set<() => void>();
// The snapshot must be the same object while the stored text is the same, or React renders forever.
let cachedRaw: string | null = null;
let cached: MyListing[] = [];

function isMyListing(value: unknown): value is MyListing {
  const listing = value as MyListing | null;
  return (
    typeof listing?.id === "string" &&
    typeof listing.input?.text === "string" &&
    STATUSES.includes(listing.status) &&
    typeof listing.updatedAt === "string"
  );
}

function readRaw(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function parse(raw: string | null): MyListing[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isMyListing) : [];
  } catch {
    return [];
  }
}

export function myListings(): MyListing[] {
  const raw = readRaw();
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cached = parse(raw);
  }
  return cached;
}

function write(listings: MyListing[]): void {
  const raw = JSON.stringify(listings);
  try {
    localStorage.setItem(KEY, raw);
  } catch {
    // Storage refused (private mode, quota): the list lives until the page is closed.
  }
  cachedRaw = readRaw() === raw ? raw : cachedRaw;
  cached = listings;
  listeners.forEach((listener) => listener());
}

function update(id: string, change: (listing: MyListing) => MyListing): MyListing {
  const current = myListings().find((listing) => listing.id === id);
  if (!current) throw new Error(`No listing ${id} in "Mis anuncios"`);
  const updated = { ...change(current), updatedAt: new Date().toISOString() };
  write(myListings().map((listing) => (listing.id === id ? updated : listing)));
  return updated;
}

const newId = () =>
  typeof crypto?.randomUUID === "function" ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

export function findMyListing(id: string): MyListing | undefined {
  return myListings().find((listing) => listing.id === id);
}

/** A new draft, or the new text of an existing one: a changed text is a draft again, whatever it was. */
export function saveDraft(input: ListingInput, id?: string): MyListing {
  if (id && findMyListing(id)) {
    return update(id, (listing) =>
      // The quick review was of the old text: it goes with it.
      JSON.stringify(listing.input) === JSON.stringify(input) ? listing : { ...listing, input, status: "draft", quickReview: undefined },
    );
  }
  const created: MyListing = { id: newId(), input, status: "draft", updatedAt: new Date().toISOString() };
  write([...myListings(), created]);
  return created;
}

export function recordQuickReview(id: string, review: ListingReview): MyListing {
  return update(id, (listing) => ({ ...listing, quickReview: review }));
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  // Another tab of the same browser saved a listing: this one shows it too.
  const onStorage = (event: StorageEvent) => event.key === KEY && listener();
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function useMyListings(): MyListing[] {
  return useSyncExternalStore(subscribe, myListings, myListings);
}
