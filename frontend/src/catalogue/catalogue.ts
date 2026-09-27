/**
 * The marketplace's catalogue: the fictional rentals a tenant browses, and how they are searched.
 *
 * The listings are fake on purpose (see `listings.ts`); the search over them is real, so the pages
 * built on top behave like the ones of a marketplace with a database behind. The listings the
 * landlord published in this browser are searched with them.
 */

import { publishedListings } from "../landlord/myListingsStore";
import { CATALOGUE } from "./listings";

export type EnergyRating = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "En trámite" | "Exenta";

export type Agency = {
  name: string;
  // Shown in the agency badge instead of a logo: the agencies are fictional and have none.
  initials: string;
};

export type RentalListing = {
  id: string;
  title: string;
  municipality: string;
  // The autonomous community: it decides which regional law applies to the listing.
  region: string;
  neighbourhood: string;
  priceEurMonth: number;
  usableSurfaceM2: number;
  rooms: number;
  bathrooms: number;
  floor: string;
  // Null when the listing does not state it, which is itself something to review.
  energyRating: EnergyRating | null;
  features: string[];
  agency: Agency;
  // Paths under `public/photos/`, the first one is the cover.
  photos: string[];
  // As the landlord or the agency wrote it: the text the review and the Q&A read.
  description: string;
  // ISO date (YYYY-MM-DD).
  publishedAt: string;
  // Published by the landlord of this browser, after the agent's review: marked as theirs.
  mine?: boolean;
};

export type SearchFilters = {
  municipality?: string;
  maxPrice?: number;
  minRooms?: number;
  minSurface?: number;
};

export type SortOrder = "recent" | "price_asc" | "price_desc" | "surface_desc";

// "malaga" finds "Málaga" and "PALMA" finds "Palma": nobody types the accents in a search box.
const normalised = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .trim()
    .toLowerCase();

const COMPARATORS: Record<SortOrder, (a: RentalListing, b: RentalListing) => number> = {
  recent: (a, b) => b.publishedAt.localeCompare(a.publishedAt),
  price_asc: (a, b) => a.priceEurMonth - b.priceEurMonth,
  price_desc: (a, b) => b.priceEurMonth - a.priceEurMonth,
  surface_desc: (a, b) => b.usableSurfaceM2 - a.usableSurfaceM2,
};

const allListings = () => [...CATALOGUE, ...publishedListings()];

export function searchListings(filters: SearchFilters, sort: SortOrder = "recent"): RentalListing[] {
  const municipality = filters.municipality ? normalised(filters.municipality) : undefined;
  return allListings().filter(
    (listing) =>
      (municipality === undefined || normalised(listing.municipality) === municipality) &&
      (filters.maxPrice === undefined || listing.priceEurMonth <= filters.maxPrice) &&
      (filters.minRooms === undefined || listing.rooms >= filters.minRooms) &&
      (filters.minSurface === undefined || listing.usableSurfaceM2 >= filters.minSurface),
  ).sort(COMPARATORS[sort]);
}

export function findListing(id: string): RentalListing | undefined {
  return allListings().find((listing) => listing.id === id);
}

/** Every municipality with at least one listing, alphabetically, as the search box offers them. */
export function municipalities(): string[] {
  const names = allListings().map((listing) => listing.municipality).filter(Boolean);
  return [...new Set(names)].sort((a, b) => a.localeCompare(b, "es"));
}

/** Where a listing is, as far as it says: a landlord's own listing names no neighbourhood. */
export function placeOf(listing: RentalListing): string {
  return [listing.neighbourhood, listing.municipality].filter(Boolean).join(", ");
}
