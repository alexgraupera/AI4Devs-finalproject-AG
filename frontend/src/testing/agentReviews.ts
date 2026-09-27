/** Agent reviews as the API returns them, one per outcome, for the tests of the publishing flow. */

import type { AgentReview, CitedFinding } from "../api/types";

const DEPOSIT: CitedFinding = {
  category: "deposit_and_guarantees",
  severity: "high",
  message: "La fianza de dos mensualidades supera la legal",
  suggestion: "Pide una mensualidad de fianza.",
  legal_basis: "LAU art. 36.1",
  citations: [
    {
      law_id: "BOE-A-1994-26003",
      law_title: "Ley 29/1994, de 24 de noviembre, de Arrendamientos Urbanos.",
      article: "Artículo 36. Fianza",
      url: "https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
      chunk_id: 7,
    },
  ],
};

const FEES: CitedFinding = {
  category: "agency_fees",
  severity: "high",
  message: "Los gastos de agencia no pueden cobrarse al inquilino",
  suggestion: "Indica que los gastos de gestión los paga la propiedad.",
  legal_basis: "LAU art. 20.1",
  citations: [
    {
      law_id: "BOE-A-1994-26003",
      law_title: "Ley 29/1994, de 24 de noviembre, de Arrendamientos Urbanos.",
      article: "Artículo 20. Gastos generales y de servicios individuales",
      url: "https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a20",
      chunk_id: 9,
    },
  ],
};

const COMMON = {
  request_id: "agent-1",
  run_id: null,
  stop_reason: "completed",
  escalated: false,
  dropped_findings: 0,
  disputed_findings: [],
  pending_review: null,
  human_decision: null,
  rewrite: null,
  usage: {
    provider: "anthropic",
    model: "claude-haiku-4-5",
    input_tokens: 21000,
    output_tokens: 1400,
    latency_ms: 14800,
    estimated_cost_usd: "0.0251",
    attempts: 4,
  },
  trace: [
    { step: 1, tool: "check_listing_fields", arguments: {}, result: "Faltan: calificación energética", ok: true, latency_ms: 2, thought: null },
    {
      step: 2,
      tool: "search_regulations",
      arguments: { query: "fianza vivienda" },
      result: "[1] LAU art. 36. Fianza…",
      ok: true,
      latency_ms: 850,
      thought: "Compruebo el límite de la fianza.",
    },
    { step: 3, tool: "critic", arguments: {}, result: "Duda de 1 incidencia", ok: false, latency_ms: 2100, thought: null },
  ],
  cost_breakdown: [
    { step: "plan", calls: 3, input_tokens: 18000, output_tokens: 1100, latency_ms: 9000, estimated_cost_usd: "0.0215" },
    { step: "tools", calls: 2, input_tokens: 0, output_tokens: 0, latency_ms: 852, estimated_cost_usd: "0" },
    { step: "critic", calls: 1, input_tokens: 3000, output_tokens: 300, latency_ms: 2100, estimated_cost_usd: "0.0036" },
  ],
} satisfies Partial<AgentReview>;

export const AGENT_APPROVED: AgentReview = {
  ...COMMON,
  status: "completed",
  findings: [],
  verdict: "approve",
  summary: "El anuncio incluye la información obligatoria y no pide nada que la ley no permita.",
};

export const AGENT_CHANGES: AgentReview = {
  ...COMMON,
  request_id: "agent-2",
  status: "completed",
  findings: [DEPOSIT, FEES],
  verdict: "request_changes",
  summary: "El anuncio pide una fianza por encima de la legal y cobra los gastos de agencia al inquilino.",
  dropped_findings: 1,
  rewrite: {
    text: "Piso exterior de 2 habitaciones en Arganzuela (Madrid). Fianza de una mensualidad. Certificado energético [calificación].",
    changes: ["Fianza de una mensualidad", "Gastos de agencia a cargo de la propiedad"],
    placeholders: ["calificación energética"],
    new_figures: ["1.000 €"],
  },
};

export const AGENT_PAUSED: AgentReview = {
  ...COMMON,
  request_id: "agent-3",
  status: "waiting_human",
  run_id: "run-42",
  escalated: true,
  findings: [DEPOSIT, FEES],
  verdict: "request_changes",
  summary: "El anuncio pide una fianza por encima de la legal y cobra los gastos de agencia al inquilino.",
  disputed_findings: [
    {
      message: FEES.message,
      legal_basis: FEES.legal_basis,
      problem: "not_in_listing",
      reason: "El anuncio no dice quién paga la agencia.",
    },
  ],
  pending_review: {
    run_id: "run-42",
    reason: "El revisor no ha podido respaldar todas las conclusiones del agente con el anuncio y la normativa.",
    proposed: {
      findings: [DEPOSIT, FEES],
      verdict: "request_changes",
      summary: "El anuncio pide una fianza por encima de la legal y cobra los gastos de agencia al inquilino.",
      rewrite: null,
    },
    rejected: [
      { message: FEES.message, legal_basis: FEES.legal_basis, problem: "not_in_listing", reason: "El anuncio no dice quién paga la agencia." },
    ],
  },
};
