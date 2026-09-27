/**
 * What a tenant is likely to ask about a listing, read from the listing itself, and which laws apply
 * to it. The questions are phrased the way the regulation Q&A answers best: one topic each, in the
 * words of the law. Checked against the real API on 2026-09-27: all of them are answered with their
 * article, but "¿Quién paga los honorarios de la agencia?" was not; "gastos de gestión inmobiliaria",
 * the wording of LAU art. 20.1, is.
 */

import type { Jurisdiction } from "../api/types";
import type { RentalListing } from "../catalogue/catalogue";

export const DEPOSIT_QUESTION = "¿Cuánta fianza y qué garantías adicionales me pueden pedir?";
export const FEES_QUESTION = "¿Quién paga los gastos de gestión inmobiliaria y de formalización del contrato?";
export const ENERGY_QUESTION = "¿Es obligatorio que el anuncio indique la calificación energética?";
export const CATALAN_OFFER_QUESTION = "¿Qué información debe incluir una oferta de alquiler de vivienda en Cataluña?";
export const MINIMUM_INFORMATION_QUESTION = "¿Qué información me tienen que dar antes de firmar el contrato?";

const CATALONIA = "Cataluña";

const mentions = (text: string, pattern: RegExp) =>
  pattern.test(
    text
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .toLowerCase(),
  );

export function jurisdictionsOf(listing: RentalListing): Jurisdiction[] {
  return listing.region === CATALONIA ? ["state", "catalonia"] : ["state"];
}

export function suggestedQuestions(listing: RentalListing): string[] {
  const questions: string[] = [];
  if (mentions(listing.description, /fianza|garantia|aval/)) questions.push(DEPOSIT_QUESTION);
  if (mentions(listing.description, /honorarios|gastos de gestion/)) questions.push(FEES_QUESTION);
  if (listing.energyRating === null || listing.energyRating === "En trámite") questions.push(ENERGY_QUESTION);
  if (listing.region === CATALONIA) questions.push(CATALAN_OFFER_QUESTION);
  questions.push(MINIMUM_INFORMATION_QUESTION);
  return questions;
}
