/**
 * What the API answers, as the frontend reads it. Mirrors the response models of `app/api/`: the
 * field names are the API's, in snake_case, so a change there is a search away from here.
 */

export type Jurisdiction = "state" | "catalonia";

export type Usage = {
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  // A decimal, serialised as a string so it keeps its precision; null when the model has no price.
  estimated_cost_usd: string | null;
  // 0 when no model was called: nothing in the corpus passed the threshold.
  attempts: number;
};

export type Citation = {
  law_id: string;
  law_title: string;
  article: string;
  url: string;
  chunk_id: number;
};

export type RetrievedSummary = {
  chunk_id: number;
  article_title: string;
  law_id: string;
  score: number;
};

export type RegulationAnswer = {
  request_id: string | null;
  answer: string;
  citations: Citation[];
  has_answer: boolean;
  usage: Usage;
  retrieved: RetrievedSummary[];
};

export type FeedbackKind = "listing_review" | "agent_review" | "regulation_answer";

export type FeedbackVote = {
  request_id: string;
  kind: FeedbackKind;
  rating: "up" | "down";
  comment: string | null;
};

/** A listing as the review takes it: the text as written, plus the structured fields a portal form has. */
export type ListingInput = {
  text: string;
  price_eur_month: number | null;
  usable_surface_m2: number | null;
  rooms: number | null;
  municipality: string | null;
  energy_rating: string | null;
};

export type Severity = "high" | "medium" | "low";
export type Verdict = "approve" | "request_changes";

export type Finding = {
  category: string;
  severity: Severity;
  message: string;
  suggestion: string;
  // The article that backs it, e.g. "LAU art. 36.1"; null when the finding is not a legal one.
  legal_basis: string | null;
};

export type ListingReview = {
  request_id: string | null;
  findings: Finding[];
  verdict: Verdict;
  summary: string;
  usage: Usage;
  // An identical listing was reviewed before: this answer comes from the cache and cost nothing.
  cached: boolean;
};
