import type { ReactNode } from "react";
import type { Finding, ListingReview, Severity, Verdict } from "../api/types";
import { Feedback } from "./Feedback";
import { SEVERITY_LABELS, VERDICT_LABELS } from "../landlord/labels";
import { formatUsage } from "./format";

export const NO_FINDINGS = "No se han detectado incidencias.";
export const CACHED = "Respuesta cacheada · sin coste";

const SEVERITY_STYLES: Record<Severity, string> = {
  high: "bg-danger-soft text-danger",
  medium: "bg-warn-soft text-warn",
  low: "bg-canvas-sunken text-ink-soft",
};

// The most serious first: what blocks publication is read before what polishes it.
const SEVERITY_ORDER: Severity[] = ["high", "medium", "low"];

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${verdict === "approve" ? "bg-ok-soft text-ok" : "bg-warn-soft text-warn"}`}
    >
      {VERDICT_LABELS[verdict]}
    </span>
  );
}

export function FindingItem({ finding, children }: { finding: Finding; children?: ReactNode }) {
  return (
    <li className="space-y-2 rounded-xl border border-line bg-canvas p-4">
      <p className="flex items-start gap-2">
        <span className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold ${SEVERITY_STYLES[finding.severity]}`}>
          {SEVERITY_LABELS[finding.severity]}
        </span>
        <span className="font-medium">{finding.message}</span>
      </p>
      <p className="text-sm text-ink-soft">
        <span className="font-semibold text-ink">Sugerencia:</span> {finding.suggestion}
      </p>
      {finding.legal_basis && <p className="text-xs text-muted">Base legal: {finding.legal_basis}</p>}
      {children}
    </li>
  );
}

function sortedFindings<T extends Finding>(findings: T[]): T[] {
  return [...findings].sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));
}

/** The quick review of a listing: the verdict first, then each finding with what to do and the norm behind it. */
export function ReviewResult({ review }: { review: ListingReview }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <VerdictBadge verdict={review.verdict} />
        <p className="text-ink-soft">{review.summary}</p>
      </div>
      {review.findings.length === 0 ? (
        <p className="rounded-xl bg-ok-soft p-4 text-sm text-ok">{NO_FINDINGS}</p>
      ) : (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Incidencias ({review.findings.length})</h3>
          <ul className="space-y-2">
            {sortedFindings(review.findings).map((finding, position) => (
              <FindingItem key={`${position}-${finding.message}`} finding={finding} />
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-muted">{review.cached ? CACHED : formatUsage(review.usage)}</p>
      <Feedback key={review.request_id} kind="listing_review" requestId={review.request_id} />
    </div>
  );
}
