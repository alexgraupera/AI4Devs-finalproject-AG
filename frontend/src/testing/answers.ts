/** Regulation answers as the API returns them, for the tests of the pages and components that show them. */

import type { RegulationAnswer } from "../api/types";

export const ANSWERED: RegulationAnswer = {
  request_id: "req-1",
  answer: "La fianza es de una mensualidad de renta en el arrendamiento de vivienda.",
  citations: [
    {
      law_id: "BOE-A-1994-26003",
      law_title: "Ley de Arrendamientos Urbanos.",
      article: "Artículo 36. Fianza",
      url: "https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
      chunk_id: 7,
    },
  ],
  has_answer: true,
  usage: {
    provider: "anthropic",
    model: "claude-haiku-4-5",
    input_tokens: 1200,
    output_tokens: 90,
    latency_ms: 2100,
    estimated_cost_usd: "0.0017",
    attempts: 1,
  },
  retrieved: [{ chunk_id: 7, article_title: "Artículo 36. Fianza", law_id: "BOE-A-1994-26003", score: 0.71 }],
};

export const NOT_COVERED: RegulationAnswer = {
  ...ANSWERED,
  request_id: "req-2",
  answer: "No he encontrado la respuesta en la normativa indexada.",
  citations: [],
  has_answer: false,
  usage: { ...ANSWERED.usage, attempts: 0 },
  retrieved: [],
};

/** Another answer, with its own request id, for a second question in the same conversation. */
export const ANSWERED_FEES: RegulationAnswer = {
  ...ANSWERED,
  request_id: "req-3",
  answer: "Los gastos de gestión inmobiliaria son a cargo del arrendador.",
  citations: [{ ...ANSWERED.citations[0], article: "Artículo 20. Gastos generales", chunk_id: 9 }],
};
