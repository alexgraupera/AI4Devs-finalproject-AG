/** How a landlord's listing, which has only its text and a few fields, is named and placed in the marketplace. */

import type { Finding, ListingInput, Severity } from "../api/types";

/** A listing has no title of its own: its first sentence is what the landlord recognises it by. */
export function listingTitle(input: ListingInput): string {
  const firstSentence = input.text.split(/(?<=\.)\s/)[0].replace(/\.$/, "");
  return firstSentence.length > 90 ? `${firstSentence.slice(0, 87)}…` : firstSentence;
}

// The Catalan municipalities a demo listing is likely to name. The region decides whether the tenant's
// questions also search the Catalan law (Ley 18/2007); anywhere else, state law only.
const CATALAN_MUNICIPALITIES = new Set(
  [
    "Barcelona",
    "Badalona",
    "Castelldefels",
    "Girona",
    "Granollers",
    "L'Hospitalet de Llobregat",
    "Lleida",
    "Manresa",
    "Mataró",
    "Reus",
    "Sabadell",
    "Sant Cugat del Vallès",
    "Sitges",
    "Tarragona",
    "Terrassa",
  ].map((name) => name.toLocaleLowerCase("es")),
);

export function regionOf(municipality: string | null): string {
  return municipality && CATALAN_MUNICIPALITIES.has(municipality.trim().toLocaleLowerCase("es")) ? "Cataluña" : "";
}

const SEVERITY_ORDER: Severity[] = ["high", "medium", "low"];

/** The most serious first: what blocks publication is read before what polishes it. */
export function bySeverity<T extends Finding>(findings: T[]): T[] {
  return [...findings].sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));
}
