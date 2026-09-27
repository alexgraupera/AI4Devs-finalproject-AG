import { useEffect, useEffectEvent, useId, useState } from "react";
import { Link } from "react-router";
import { ApiError, pendingAgentReview, resumeAgentReview, UNEXPECTED_ERROR } from "../api/client";
import type { AgentReview, HumanDecision } from "../api/types";
import { Citations, Doubt } from "../components/AgentReviewResult";
import { formatNumber } from "../components/format";
import { SeverityChip } from "../components/ReviewResult";
import { ServiceBanner } from "../components/ServiceBanner";
import { listingTitle } from "../landlord/describe";
import {
  pendingModeration,
  recordModeration,
  returnToDraft,
  useMyListings,
  type MyListing,
  type MyListingStatus,
} from "../landlord/myListingsStore";

export const NO_PENDING = "No hay revisiones pendientes.";
export const RUN_GONE = "Esta revisión ya no está disponible. El anuncio vuelve a borrador para enviarlo de nuevo.";

type Decided = {
  id: string;
  title: string;
  action: HumanDecision["action"] | "gone";
  status: MyListingStatus;
  findings: number;
};

function outcomeText({ action, status, findings }: Decided): string {
  if (action === "gone") return RUN_GONE;
  if (action === "reject") return "Revisión descartada: el anuncio vuelve a borrador.";
  const decided = action === "approve" ? "Revisión aprobada" : "Revisión ajustada";
  return status === "published"
    ? `${decided}: sin incidencias graves, el anuncio se ha publicado.`
    : `${decided}: el anuncio vuelve a su anunciante con ${findings} incidencias.`;
}

// A run the API no longer has (404), or one already decided elsewhere (409): nothing left to decide here.
const runIsGone = (failure: unknown) => failure instanceof ApiError && (failure.status === 404 || failure.status === 409);

function ModerationItem({ listing, onDecided }: { listing: MyListing; onDecided: (decided: Decided) => void }) {
  const runId = listing.runId!;
  const noteId = useId();
  const title = listingTitle(listing.input);
  const [review, setReview] = useState<AgentReview | undefined>(listing.agentReview);
  const [keep, setKeep] = useState<Set<number>>(() => new Set(listing.agentReview?.findings.map((_, index) => index)));
  const [note, setNote] = useState("");
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const gone = () => {
    returnToDraft(listing.id);
    onDecided({ id: listing.id, title, action: "gone", status: "draft", findings: 0 });
  };
  // Read by the effect below when the API answers, with whatever the listing is by then.
  const onGone = useEffectEvent(gone);

  // The API holds the paused run: what is decided is what it has, not the browser's copy of it.
  useEffect(() => {
    let active = true;
    pendingAgentReview(runId)
      .then((fresh) => {
        if (!active) return;
        setReview(fresh);
        setKeep(new Set(fresh.findings.map((_, index) => index)));
      })
      .catch((failure) => {
        if (!active) return;
        if (runIsGone(failure)) onGone();
        else setError(failure instanceof ApiError ? failure.message : UNEXPECTED_ERROR);
      });
    return () => {
      active = false;
    };
  }, [runId]);

  const decide = async (action: HumanDecision["action"]) => {
    const decision: HumanDecision = { action };
    if (action === "adjust") decision.keep = [...keep].sort((a, b) => a - b);
    if (note.trim()) decision.note = note.trim();
    setDeciding(true);
    setError(null);
    try {
      const final = await resumeAgentReview(runId, decision);
      const recorded = recordModeration(listing.id, final);
      onDecided({ id: listing.id, title, action, status: recorded.status, findings: final.findings.length });
    } catch (failure) {
      if (runIsGone(failure)) gone();
      else setError(failure instanceof ApiError ? failure.message : UNEXPECTED_ERROR);
      setDeciding(false);
    }
  };

  const toggle = (index: number) =>
    setKeep((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });

  const findings = review?.findings ?? [];
  const doubts = new Map(review?.disputed_findings.map((doubt) => [doubt.message, doubt]));
  const proposed = new Set(findings.map((finding) => finding.message));
  const removed = review?.pending_review?.rejected.filter((rejected) => !proposed.has(rejected.message)) ?? [];
  const { municipality, price_eur_month, usable_surface_m2 } = listing.input;

  return (
    <article aria-label={title} className="space-y-5 rounded-2xl border border-line bg-canvas p-5 shadow-sm sm:p-6">
      <header className="space-y-2">
        <h2 className="text-lg leading-snug font-semibold">{title}</h2>
        <p className="text-sm text-muted">
          {[
            municipality,
            price_eur_month !== null && `${formatNumber(price_eur_month)} €/mes`,
            usable_surface_m2 !== null && `${formatNumber(usable_surface_m2)} m²`,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <p className="rounded-xl bg-canvas-soft p-3 text-sm leading-relaxed whitespace-pre-line text-ink-soft">
          {listing.input.text}
        </p>
      </header>

      {review?.pending_review && (
        <p className="rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
          <span className="font-semibold">Motivo:</span> {review.pending_review.reason}
        </p>
      )}

      <fieldset disabled={deciding} className="space-y-3">
        <legend className="mb-2 text-sm font-semibold">Incidencias propuestas</legend>
        <p className="text-xs text-muted">Desmarca las que no deban mantenerse.</p>
        <ul className="space-y-2">
          {findings.map((finding, index) => (
            <li key={`${index}-${finding.message}`} className="space-y-2 rounded-xl border border-line p-4">
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={keep.has(index)}
                  onChange={() => toggle(index)}
                  className="mt-1 size-4 accent-ink"
                />
                <span className="flex items-start gap-2">
                  <SeverityChip severity={finding.severity} />
                  <span className="font-medium">{finding.message}</span>
                </span>
              </label>
              <p className="pl-7 text-sm text-ink-soft">
                <span className="font-semibold text-ink">Sugerencia:</span> {finding.suggestion}
              </p>
              {finding.legal_basis && <p className="pl-7 text-xs text-muted">Base legal: {finding.legal_basis}</p>}
              <div className="space-y-2 pl-7">
                <Citations finding={finding} />
                {doubts.has(finding.message) && <Doubt doubt={doubts.get(finding.message)!} />}
              </div>
            </li>
          ))}
        </ul>
        {removed.length > 0 && (
          <details className="text-sm">
            <summary className="cursor-pointer text-ink-soft">Descartadas por el revisor ({removed.length})</summary>
            <ul className="mt-2 space-y-1 pl-5 text-muted">
              {removed.map((rejected) => (
                <li key={rejected.message}>
                  <s>{rejected.message}</s>: {rejected.reason}
                </li>
              ))}
            </ul>
          </details>
        )}

        <div className="space-y-1">
          <label htmlFor={noteId} className="text-xs font-medium text-muted">
            Nota para el anunciante (opcional)
          </label>
          <textarea
            id={noteId}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={500}
            rows={2}
            className="w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void decide("approve")}
            className="rounded-lg bg-ink px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-soft disabled:opacity-60"
          >
            Aprobar la revisión
          </button>
          <button
            type="button"
            // Keeping every finding is approving; keeping only some is the adjustment.
            disabled={keep.size === findings.length}
            onClick={() => void decide("adjust")}
            className="rounded-lg border border-line bg-canvas px-4 py-2.5 text-sm font-medium hover:border-ink-soft disabled:opacity-50"
          >
            Mantener solo las marcadas
          </button>
          <button
            type="button"
            onClick={() => void decide("reject")}
            className="rounded-lg px-4 py-2.5 text-sm font-medium text-danger hover:bg-danger-soft disabled:opacity-60"
          >
            Descartar la revisión
          </button>
        </div>
      </fieldset>

      {deciding && (
        <p role="status" className="text-sm text-muted">
          Reanudando la revisión con tu decisión…
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}
    </article>
  );
}

/**
 * The quality team's queue: the reviews the agent paused because its critic could not back every
 * conclusion (ADR 0027). A person decides which findings stand, and the listing follows the review.
 */
export function ModerationPage() {
  const pending = pendingModeration(useMyListings());
  const [decided, setDecided] = useState<Decided[]>([]);

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-12">
      <header className="space-y-3">
        <p>
          <span className="rounded-full bg-panel px-2.5 py-1 text-xs font-semibold text-panel-text">Equipo</span>
        </p>
        <h1 className="text-4xl font-semibold tracking-tight">Moderación</h1>
        <p className="text-lg text-muted">Revisiones que esperan a una persona</p>
        <p className="text-sm text-ink-soft">
          El agente pausa una revisión cuando el revisor, un segundo modelo de otro proveedor, no puede respaldar todas
          sus conclusiones con el anuncio y la normativa. Tú decides qué incidencias se mantienen, y el anuncio sigue la
          revisión final: sin incidencias graves se publica; con ellas, vuelve a su anunciante.
        </p>
      </header>

      <ServiceBanner />

      {decided.length > 0 && (
        <ul aria-label="Decisiones" className="space-y-2">
          {decided.map((item) => (
            <li key={item.id} role="status" className="rounded-xl bg-canvas-sunken px-4 py-3 text-sm text-ink-soft">
              <span className="font-medium text-ink">{item.title}.</span> {outcomeText(item)}{" "}
              <Link to={`/publicar/${item.id}`} className="font-medium text-accent-strong underline-offset-2 hover:underline">
                Ver el anuncio
              </Link>
            </li>
          ))}
        </ul>
      )}

      {pending.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-line px-6 py-16 text-center text-ink-soft">{NO_PENDING}</p>
      ) : (
        <ol aria-label="Revisiones pendientes" className="space-y-6">
          {pending.map((listing) => (
            <li key={listing.id}>
              <ModerationItem listing={listing} onDecided={(item) => setDecided((current) => [item, ...current])} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
