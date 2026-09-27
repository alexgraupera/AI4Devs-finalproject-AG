/** How the review and the publishing workflow are named to the landlord. */

import type { Severity, Verdict } from "../api/types";
import type { MyListingStatus } from "./myListingsStore";

export const VERDICT_LABELS: Record<Verdict, string> = {
  approve: "Listo para publicar",
  request_changes: "Requiere cambios",
};

export const SEVERITY_LABELS: Record<Severity, string> = { high: "Alta", medium: "Media", low: "Baja" };

export const STATUS_LABELS: Record<MyListingStatus, string> = {
  draft: "Borrador",
  changes_requested: "Requiere cambios",
  pending_moderation: "Pendiente de moderación",
  published: "Publicado",
};

/** The steps of the agent, named for the person reading the review rather than by their tool. */
export const TOOL_LABELS: Record<string, string> = {
  check_listing_fields: "Comprobar los datos del anuncio",
  search_regulations: "Consultar la normativa",
  submit_review: "Entregar la revisión",
  critic: "Comprobación de las incidencias contra el anuncio y la normativa",
  boss: "Decisión sobre la revisión",
  rewrite: "Corregir el anuncio",
  "(sin herramienta)": "Respuesta sin herramienta",
};

// What a step marked as not ok means depends on the step: a failed tool call is not a critic that
// doubted a finding, and saying "failed and retried" of the latter is simply false.
export const FAILURE_NOTE = "Esta llamada ha fallado: el agente ha recibido el error y ha seguido.";
export const FAILURE_NOTES: Record<string, string> = {
  critic: "El revisor no respalda alguna incidencia; el motivo está en la revisión.",
  rewrite: "El anuncio corregido tiene cifras que el original no tenía: revísalas antes de publicarlo.",
  "(sin herramienta)": "El agente contestó sin usar ninguna herramienta y se le pidió que entregara la revisión.",
};

/** Where a review spends: the actor's turns, the tools, the critic and the rewrite (#52). */
export const COST_STEP_LABELS: Record<string, string> = {
  plan: "Razonamiento del agente",
  tools: "Herramientas",
  critic: "Revisor",
  rewrite: "Anuncio corregido",
};
