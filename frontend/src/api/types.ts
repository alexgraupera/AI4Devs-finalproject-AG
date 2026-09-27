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

export type CitedFinding = Finding & {
  // The articles the agent read before stating it, as the search returned them: never written by the model.
  citations: Citation[];
};

/** A finding the critic did not back, with why: kept for the person deciding (flag mode, ADR 0035). */
export type RejectedFinding = {
  message: string;
  legal_basis: string | null;
  problem: string;
  reason: string;
};

export type ListingRewrite = {
  text: string;
  changes: string[];
  // Data the agent may not invent, left as gaps in square brackets.
  placeholders: string[];
  // Figures in the rewrite that the original does not state: to check before publishing.
  new_figures: string[];
};

export type TraceStep = {
  step: number;
  tool: string;
  arguments: Record<string, unknown>;
  result: string;
  ok: boolean;
  latency_ms: number;
  thought: string | null;
};

export type StepCost = {
  step: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  estimated_cost_usd: string | null;
};

export type HumanReviewRequest = {
  run_id: string;
  reason: string;
  proposed: { findings: CitedFinding[]; verdict: Verdict; summary: string; rewrite: ListingRewrite | null };
  rejected: RejectedFinding[];
};

/**
 * What a person decides on a paused review: approve its findings, keep only some (their positions in
 * the proposed list, from 0), or reject it. The note is for the landlord.
 */
export type HumanDecision = {
  action: "approve" | "adjust" | "reject";
  keep?: number[];
  note?: string;
};

// completed; waiting_human: paused before publishing, for a person to decide; discarded: a person rejected it.
export type AgentReviewStatus = "completed" | "waiting_human" | "discarded";

export type AgentReview = {
  request_id: string | null;
  status: AgentReviewStatus;
  run_id: string | null;
  findings: CitedFinding[];
  verdict: Verdict;
  summary: string;
  trace: TraceStep[];
  stop_reason: string;
  escalated: boolean;
  dropped_findings: number;
  disputed_findings: RejectedFinding[];
  pending_review: HumanReviewRequest | null;
  human_decision: { action: HumanDecision["action"]; keep: number[] | null; note: string | null } | null;
  rewrite: ListingRewrite | null;
  usage: Usage;
  cost_breakdown: StepCost[];
};
