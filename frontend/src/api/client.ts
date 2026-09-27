/**
 * How the frontend talks to the AI service: always through the marketplace's web server (`web/`),
 * which adds the credentials. The browser never sees them, so it never sends them either.
 */

import type { FeedbackVote, Jurisdiction, ListingInput, ListingReview, RegulationAnswer } from "./types";

export const UNEXPECTED_ERROR = "No se ha podido contactar con el servicio. Inténtalo de nuevo.";

/** A failed call, with the message to show: the API's own words when it gave any. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function messageOf(body: unknown): string | undefined {
  const message = (body as { error?: { message?: unknown } } | null)?.error?.message;
  return typeof message === "string" ? message : undefined;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError(UNEXPECTED_ERROR, 0);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(messageOf(body) ?? UNEXPECTED_ERROR, response.status);
  if (body === null) throw new ApiError(UNEXPECTED_ERROR, response.status);
  return body as T;
}

const post = <T>(path: string, payload: unknown) =>
  call<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });

/** `jurisdictions` null searches every law in the corpus. */
export function askRegulations(question: string, jurisdictions: Jurisdiction[] | null): Promise<RegulationAnswer> {
  return post<RegulationAnswer>("/api/v1/regulations/ask", { question, jurisdictions });
}

/** The quick review: the CAG pipeline, a few seconds and a fraction of a cent, to run as often as needed. */
export function reviewListing(listing: ListingInput): Promise<ListingReview> {
  return post<ListingReview>("/api/v1/listings/review", listing);
}

export async function sendFeedback(vote: FeedbackVote): Promise<void> {
  await post<unknown>("/api/v1/feedback", vote);
}

/** Whether the API answers. The web server waits for a sleeping free-tier API to wake before it says. */
export async function serviceStatus(): Promise<"up" | "down"> {
  try {
    const { api } = await call<{ api: "up" | "down" }>("/bff/service");
    return api;
  } catch {
    return "down";
  }
}
