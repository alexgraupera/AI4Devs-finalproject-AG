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
