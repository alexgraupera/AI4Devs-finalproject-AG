/** Quick reviews as the API returns them, for the tests of the landlord's pages. */

import type { ListingReview } from "../api/types";

const USAGE = {
  provider: "anthropic",
  model: "claude-haiku-4-5",
  input_tokens: 2400,
  output_tokens: 300,
  latency_ms: 3400,
  estimated_cost_usd: "0.0035",
  attempts: 1,
};

export const CHANGES_REQUESTED: ListingReview = {
  request_id: "rev-1",
  verdict: "request_changes",
  summary: "El anuncio pide una fianza por encima de la legal.",
  findings: [
    {
      category: "description_quality",
      severity: "low",
      message: "La descripción no dice en qué planta está el piso",
      suggestion: "Indica la planta y si hay ascensor.",
      legal_basis: null,
    },
    {
      category: "deposit_and_guarantees",
      severity: "high",
      message: "La fianza de dos mensualidades supera la legal",
      suggestion: "Pide una mensualidad de fianza.",
      legal_basis: "LAU art. 36.1",
    },
  ],
  usage: USAGE,
  cached: false,
};

export const APPROVED: ListingReview = {
  request_id: "rev-2",
  verdict: "approve",
  summary: "El anuncio incluye la información obligatoria.",
  findings: [],
  usage: USAGE,
  cached: true,
};
