import type { Citation, Usage } from "../api/types";

// "always": the Spanish locale leaves four-digit numbers ungrouped (1350), and a portal writes 1.350.
const NUMBER = new Intl.NumberFormat("es-ES", { useGrouping: "always", maximumFractionDigits: 0 });
const COST = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
const DATE = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "long", year: "numeric" });

export function formatNumber(value: number): string {
  return NUMBER.format(value);
}

/** "2026-09-26" → "26 de septiembre de 2026", read as a local date so no time zone moves it a day. */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return DATE.format(new Date(year, month - 1, day));
}

/** What a model call cost and took, as every result shows it under its technical details. */
export function formatUsage(usage: Usage): string {
  const cost = usage.estimated_cost_usd === null ? "no disponible" : `${COST.format(Number(usage.estimated_cost_usd))} USD`;
  return `Modelo: ${usage.model} · ${usage.input_tokens} + ${usage.output_tokens} tokens · ${usage.latency_ms} ms · Coste estimado: ${cost}`;
}

/** "Ley 29/1994, de Arrendamientos Urbanos · Artículo 36": the BOE titles end in a full stop, a link does not. */
export function citationLabel(citation: Citation): string {
  return `${citation.law_title.replace(/\.$/, "")} · ${citation.article}`;
}
