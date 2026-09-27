import type { AgentReview, CitedFinding, ListingRewrite, RejectedFinding, StepCost, TraceStep } from "../api/types";
import { bySeverity } from "../landlord/describe";
import { COST_STEP_LABELS, FAILURE_NOTE, FAILURE_NOTES, TOOL_LABELS } from "../landlord/labels";
import { Feedback } from "./Feedback";
import { citationLabel, formatNumber, formatUsage } from "./format";
import { FindingItem, NO_FINDINGS, VerdictBadge } from "./ReviewResult";

export const PLACEHOLDERS_WARNING = "El agente no puede inventar estos datos. Complétalos antes de publicar: ";
export const NEW_FIGURES_WARNING = "Revisa estas cifras: aparecen en la versión corregida y no en tu anuncio: ";
export const USE_REWRITE = "Usar esta versión";

const DECISION_LABELS = { approve: "aprobada", adjust: "ajustada", reject: "descartada" } as const;

const COST = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
// A search result is a page of articles: its first lines say what was found, the rest is one click away.
const RESULT_PREVIEW_CHARS = 400;

function StatusBadge({ review }: { review: AgentReview }) {
  if (review.status === "waiting_human") {
    return <span className="inline-flex rounded-full bg-warn-soft px-3 py-1 text-sm font-semibold text-warn">Pendiente de moderación</span>;
  }
  if (review.status === "discarded") {
    return <span className="inline-flex rounded-full bg-canvas-sunken px-3 py-1 text-sm font-semibold text-ink-soft">Revisión descartada</span>;
  }
  return <VerdictBadge verdict={review.verdict} />;
}

export function Citations({ finding }: { finding: CitedFinding }) {
  if (finding.citations.length === 0) return null;
  return (
    <ul className="space-y-1 text-xs">
      {finding.citations.map((citation) => (
        <li key={citation.chunk_id}>
          <a href={citation.url} target="_blank" rel="noreferrer" className="text-accent-strong underline-offset-2 hover:underline">
            {citationLabel(citation)}
          </a>
        </li>
      ))}
    </ul>
  );
}

export function Doubt({ doubt }: { doubt: RejectedFinding }) {
  return (
    <p className="rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">
      <span className="font-semibold">El revisor la pone en duda:</span> {doubt.reason}
    </p>
  );
}

function Rewrite({ rewrite, onUse }: { rewrite: ListingRewrite; onUse?: (text: string) => void }) {
  return (
    <section aria-label="Anuncio corregido" className="space-y-3 rounded-xl border border-line bg-canvas p-4">
      <h3 className="text-sm font-semibold">Anuncio corregido</h3>
      {rewrite.placeholders.length > 0 && (
        <p className="rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">
          {PLACEHOLDERS_WARNING}
          {rewrite.placeholders.join(", ")}
        </p>
      )}
      {rewrite.new_figures.length > 0 && (
        <p className="rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">
          {NEW_FIGURES_WARNING}
          {rewrite.new_figures.join(", ")}
        </p>
      )}
      <p className="rounded-lg bg-canvas-soft p-3 text-sm leading-relaxed whitespace-pre-line text-ink-soft">{rewrite.text}</p>
      {rewrite.changes.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-ink-soft">Cambios aplicados</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
            {rewrite.changes.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
        </details>
      )}
      {onUse && (
        <button
          type="button"
          onClick={() => onUse(rewrite.text)}
          className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-ink-soft"
        >
          {USE_REWRITE}
        </button>
      )}
    </section>
  );
}

function Step({ step }: { step: TraceStep }) {
  const result = step.result.length > RESULT_PREVIEW_CHARS ? `${step.result.slice(0, RESULT_PREVIEW_CHARS)}…` : step.result;
  return (
    <li className="space-y-1 border-t border-line pt-2 first:border-t-0 first:pt-0">
      <p className="font-medium">
        {step.step}. {step.ok ? "✅" : "⚠️"} {TOOL_LABELS[step.tool] ?? step.tool}
      </p>
      <p className="text-xs text-muted">
        Herramienta: {step.tool} · {formatNumber(step.latency_ms)} ms
      </p>
      {step.thought && <p className="text-xs text-ink-soft italic">{step.thought}</p>}
      {!step.ok && <p className="text-xs text-warn">{FAILURE_NOTES[step.tool] ?? FAILURE_NOTE}</p>}
      {Object.keys(step.arguments).length > 0 && (
        <pre className="overflow-x-auto rounded-md bg-canvas-sunken p-2 text-[11px]">{JSON.stringify(step.arguments, null, 2)}</pre>
      )}
      {result && <p className="text-xs whitespace-pre-line text-ink-soft">{result}</p>}
    </li>
  );
}

function CostPerStep({ steps }: { steps: StepCost[] }) {
  return (
    <table className="w-full text-left text-xs">
      <caption className="mb-2 text-left text-sm font-medium text-ink-soft">Coste por paso</caption>
      <thead className="text-muted">
        <tr>
          <th className="py-1 pr-2 font-medium">Paso</th>
          <th className="py-1 pr-2 font-medium">Llamadas</th>
          <th className="py-1 pr-2 font-medium">Tokens</th>
          <th className="py-1 pr-2 font-medium">Tiempo</th>
          <th className="py-1 font-medium">Coste</th>
        </tr>
      </thead>
      <tbody>
        {steps.map((step) => (
          <tr key={step.step} className="border-t border-line">
            <td className="py-1 pr-2">{COST_STEP_LABELS[step.step] ?? step.step}</td>
            <td className="py-1 pr-2 tabular-nums">{step.calls}</td>
            <td className="py-1 pr-2 tabular-nums">{formatNumber(step.input_tokens + step.output_tokens)}</td>
            <td className="py-1 pr-2 tabular-nums">{(step.latency_ms / 1000).toFixed(1)} s</td>
            <td className="py-1 tabular-nums">
              {step.estimated_cost_usd === null ? "no disponible" : `${COST.format(Number(step.estimated_cost_usd))} USD`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type AgentReviewResultProps = {
  review: AgentReview;
  // Offered while the listing can still be edited: the corrected text replaces the one in the form.
  onUseRewrite?: (text: string) => void;
};

/**
 * The agent's review of a listing: where each finding comes from (the BOE articles the agent read),
 * what the critic doubts and why, the listing corrected, and the steps and the cost behind it.
 */
export function AgentReviewResult({ review, onUseRewrite }: AgentReviewResultProps) {
  const doubts = new Map(review.disputed_findings.map((doubt) => [doubt.message, doubt]));
  const findings = bySeverity(review.findings);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <StatusBadge review={review} />
        <p className="text-ink-soft">{review.summary}</p>
        {review.pending_review && <p className="text-sm text-muted">Motivo: {review.pending_review.reason}</p>}
        {review.human_decision && (
          <p className="rounded-lg bg-canvas-sunken px-3 py-2 text-sm text-ink-soft">
            Revisión {DECISION_LABELS[review.human_decision.action]} por el equipo de moderación.
            {review.human_decision.note && (
              <>
                {" "}
                <span className="font-semibold text-ink">Nota:</span> {review.human_decision.note}
              </>
            )}
          </p>
        )}
      </div>

      {findings.length === 0 ? (
        <p className="rounded-xl bg-ok-soft p-4 text-sm text-ok">{NO_FINDINGS}</p>
      ) : (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Incidencias ({findings.length})</h3>
          {doubts.size > 0 && (
            <p className="text-sm text-warn">El revisor pone en duda {doubts.size} de estas incidencias</p>
          )}
          <ul className="space-y-2">
            {findings.map((finding, position) => (
              <FindingItem key={`${position}-${finding.message}`} finding={finding}>
                <Citations finding={finding} />
                {doubts.has(finding.message) && <Doubt doubt={doubts.get(finding.message)!} />}
              </FindingItem>
            ))}
          </ul>
        </div>
      )}
      {review.dropped_findings > 0 && (
        <p className="text-xs text-muted">
          Se han descartado {review.dropped_findings} incidencias que el anuncio o la normativa consultada no respaldaban.
        </p>
      )}

      {review.rewrite && <Rewrite rewrite={review.rewrite} onUse={onUseRewrite} />}

      <details className="rounded-xl border border-line bg-canvas p-4 text-sm">
        <summary className="cursor-pointer font-medium text-ink-soft">Detalles técnicos</summary>
        <div className="mt-3 space-y-4 overflow-x-auto">
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-ink-soft">Pasos del agente ({review.trace.length})</h4>
            <ol className="space-y-2">
              {review.trace.map((step) => (
                <Step key={step.step} step={step} />
              ))}
            </ol>
          </div>
          {review.cost_breakdown.length > 0 && <CostPerStep steps={review.cost_breakdown} />}
          <p className="text-xs text-muted">{formatUsage(review.usage)}</p>
        </div>
      </details>

      {review.status !== "discarded" && (
        <Feedback key={review.request_id} kind="agent_review" requestId={review.request_id} />
      )}
    </div>
  );
}
