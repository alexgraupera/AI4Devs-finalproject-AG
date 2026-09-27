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
import type { AgentReview, ListingInput, ListingReview } from "../api/types";
import type { EnergyRating, RentalListing } from "../catalogue/catalogue";
import { listingTitle, regionOf } from "./describe";

const KEY = "umbral-my-listings";

export type MyListingStatus = "draft" | "changes_requested" | "pending_moderation" | "published";

export type MyListing = {
  id: string;
  input: ListingInput;
  status: MyListingStatus;
  // The last quick review, of the text as it was then. It says nothing about publishing.
  quickReview?: ListingReview;
  // The last review of the agent, which decides the status: published, changes requested or paused.
  agentReview?: AgentReview;
  // Which of the two ran last, so the page shows the newest.
  lastReview?: "quick" | "agent";
  // The paused run the moderation resumes, while the listing waits for a person.
  runId?: string;
  // ISO timestamps.
  publishedAt?: string;
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
      // The reviews were of the old text: they go with it, and a changed listing is unpublished until reviewed again.
      JSON.stringify(listing.input) === JSON.stringify(input)
        ? listing
        : { id: listing.id, input, status: "draft", updatedAt: listing.updatedAt },
    );
  }
  const created: MyListing = { id: newId(), input, status: "draft", updatedAt: new Date().toISOString() };
  write([...myListings(), created]);
  return created;
}

export function recordQuickReview(id: string, review: ListingReview): MyListing {
  return update(id, (listing) => ({ ...listing, quickReview: review, lastReview: "quick" }));
}

/**
 * The agent's review decides where the listing goes: approved is published, changes requested goes
 * back to the landlord, and a review the agent cannot stand behind waits for a person with its run id.
 */
export function recordAgentReview(id: string, review: AgentReview): MyListing {
  const status: MyListingStatus =
    review.status === "waiting_human"
      ? "pending_moderation"
      : review.status === "discarded"
        ? "draft"
        : review.verdict === "approve"
          ? "published"
          : "changes_requested";
  return update(id, (listing) => ({
    ...listing,
    agentReview: review,
    lastReview: "agent",
    status,
    runId: status === "pending_moderation" ? (review.run_id ?? undefined) : undefined,
    publishedAt: status === "published" ? new Date().toISOString() : undefined,
  }));
}

/** The listings waiting for a person, oldest first: the queue of the moderation team. */
export function pendingModeration(listings: MyListing[] = myListings()): MyListing[] {
  return listings
    .filter((listing) => listing.status === "pending_moderation" && listing.runId)
    .sort((a, b) => a.updatedAt.localeCompare(b.updatedAt));
}

/**
 * The review as a person left it: the listing follows it as it follows the agent's. Kept findings with
 * a serious one go back to the landlord, none of them publishes it, a discarded review is a draft again.
 */
export function recordModeration(id: string, review: AgentReview): MyListing {
  return recordAgentReview(id, review);
}

/** The paused run is gone (the API lost it, or it was decided elsewhere): the landlord sends it again. */
export function returnToDraft(id: string): MyListing {
  return update(id, (listing) => ({ ...listing, status: "draft", runId: undefined }));
}

const ENERGY_RATINGS: EnergyRating[] = ["A", "B", "C", "D", "E", "F", "G", "En trámite", "Exenta"];

/** A published listing as the catalogue shows it: what the landlord gave, and nothing made up. */
function asRentalListing(listing: MyListing): RentalListing {
  const { input } = listing;
  const rating = ENERGY_RATINGS.find((candidate) => candidate === input.energy_rating) ?? null;
  return {
    id: listing.id,
    title: listingTitle(input),
    municipality: input.municipality ?? "",
    region: regionOf(input.municipality),
    neighbourhood: "",
    priceEurMonth: input.price_eur_month ?? 0,
    usableSurfaceM2: input.usable_surface_m2 ?? 0,
    rooms: input.rooms ?? 0,
    bathrooms: 0,
    floor: "",
    energyRating: rating,
    features: [],
    agency: { name: "Particular", initials: "P" },
    photos: ["/photos/no-photos.svg"],
    description: input.text,
    publishedAt: (listing.publishedAt ?? listing.updatedAt).slice(0, 10),
    mine: true,
  };
}

export function publishedListings(): RentalListing[] {
  return myListings()
    .filter((listing) => listing.status === "published")
    .map(asRentalListing);
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
