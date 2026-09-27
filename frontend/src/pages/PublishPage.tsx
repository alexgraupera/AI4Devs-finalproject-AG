import { useId, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { agentReviewListing, ApiError, reviewListing, UNEXPECTED_ERROR } from "../api/client";
import type { ListingInput } from "../api/types";
import { AgentReviewResult } from "../components/AgentReviewResult";
import { ReviewResult } from "../components/ReviewResult";
import { ServiceBanner } from "../components/ServiceBanner";
import { StatusBadge } from "../components/StatusBadge";
import { EXAMPLES } from "../landlord/examples";
import {
  findMyListing,
  recordAgentReview,
  recordQuickReview,
  saveDraft,
  useMyListings,
  type MyListing,
} from "../landlord/myListingsStore";

export const EMPTY_LISTING = "El anuncio está vacío";
export const DRAFT_SAVED = "Guardado en Mis anuncios.";
export const CHANGED_SINCE_CHECK = "Has cambiado el anuncio desde la última revisión: vuelve a comprobarlo antes de enviarlo.";
export const AGENT_REVIEWING = "El agente está revisando tu anuncio: consulta la normativa y tarda unos 15 segundos.";
export const PUBLISHED = "Tu anuncio está publicado.";
export const CHANGES_REQUESTED = "El agente pide cambios antes de publicarlo: corrige las incidencias, o usa la versión corregida, y vuelve a enviarlo.";
export const PENDING_MODERATION =
  "Tu anuncio espera moderación: el agente no puede respaldar todas sus conclusiones y una persona del equipo lo revisará.";

const ENERGY_RATINGS = ["A", "B", "C", "D", "E", "F", "G", "En trámite", "Exenta"];
// The listing guardrail refuses more than this (app/foundation/guardrails/input.py).
const MAX_TEXT = 5000;

// The form keeps what the person typed, numbers included; the listing the API takes is built on submit.
type Form = {
  text: string;
  price: string;
  surface: string;
  rooms: string;
  municipality: string;
  energyRating: string;
};

const EMPTY_FORM: Form = { text: "", price: "", surface: "", rooms: "", municipality: "", energyRating: "" };

function formOf(input?: ListingInput): Form {
  if (!input) return EMPTY_FORM;
  const text = (value: number | string | null) => (value === null ? "" : `${value}`);
  return {
    text: input.text,
    price: text(input.price_eur_month),
    surface: text(input.usable_surface_m2),
    rooms: text(input.rooms),
    municipality: text(input.municipality),
    energyRating: text(input.energy_rating),
  };
}

function inputOf(form: Form): ListingInput {
  const number = (value: string) => (value.trim() === "" ? null : Number(value));
  return {
    text: form.text.trim(),
    price_eur_month: number(form.price),
    usable_surface_m2: number(form.surface),
    rooms: number(form.rooms),
    municipality: form.municipality.trim() || null,
    energy_rating: form.energyRating || null,
  };
}

const sameInput = (a: ListingInput, b: ListingInput) => JSON.stringify(a) === JSON.stringify(b);

/** Where the agent's review left the listing, said to the landlord in one line. */
function Outcome({ listing }: { listing: MyListing }) {
  if (listing.status === "published") {
    return (
      <p role="status" className="rounded-xl bg-ok-soft px-4 py-3 text-sm text-ok">
        {PUBLISHED}{" "}
        <Link to={`/alquiler/${listing.id}`} className="font-medium underline-offset-2 hover:underline">
          Verlo en la búsqueda
        </Link>
      </p>
    );
  }
  const message = { changes_requested: CHANGES_REQUESTED, pending_moderation: PENDING_MODERATION, draft: null }[
    listing.status
  ];
  return message ? (
    <p role="status" className="rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
      {message}
    </p>
  ) : null;
}

const fieldClass = "w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm text-ink";

function Field({ label, children }: { label: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-muted">
        {label}
      </label>
      {children(id)}
    </div>
  );
}

/**
 * Where a landlord writes a listing and checks it before publishing. The check is the quick review
 * (the CAG pipeline): a few seconds and a fraction of a cent, so it can run after every correction.
 * Every check saves the draft first, so "Mis anuncios" always has the text the review was of.
 */
export function PublishPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [draftId, setDraftId] = useState(id);
  const [urlId, setUrlId] = useState(id);
  const [form, setForm] = useState<Form>(() => formOf(id ? findMyListing(id)?.input : undefined));
  const [checking, setChecking] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const listing = useMyListings().find((mine) => mine.id === draftId);

  // The address changed. To the draft being edited (just saved for the first time): nothing to do.
  // To another draft, or to a new one, from the header or "Mis anuncios": the form starts from it.
  if (id !== urlId) {
    setUrlId(id);
    if (id !== draftId) {
      setDraftId(id);
      setForm(formOf(id ? findMyListing(id)?.input : undefined));
      setError(null);
      setNotice(null);
    }
  }

  if (id && !listing) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-24 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Este borrador no existe.</h1>
        <Link to="/publicar" className="mt-6 inline-block rounded-lg bg-ink px-5 py-3 text-sm font-medium text-white hover:bg-ink-soft">
          Empezar un anuncio nuevo
        </Link>
      </div>
    );
  }

  const set = (field: keyof Form) => (value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setNotice(null);
  };

  const save = (): string | null => {
    const input = inputOf(form);
    if (!input.text) {
      setError(EMPTY_LISTING);
      return null;
    }
    setError(null);
    const saved = saveDraft(input, draftId);
    if (saved.id !== draftId) {
      // The draft has an address from now on: a reload keeps editing it.
      setDraftId(saved.id);
      navigate(`/publicar/${saved.id}`, { replace: true });
    }
    return saved.id;
  };

  const saveOnly = () => {
    if (save()) setNotice(DRAFT_SAVED);
  };

  const check = async (event: FormEvent) => {
    event.preventDefault();
    const savedId = save();
    if (!savedId) return;
    setNotice(null);
    setChecking(true);
    try {
      recordQuickReview(savedId, await reviewListing(inputOf(form)));
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : UNEXPECTED_ERROR);
    } finally {
      setChecking(false);
    }
  };

  const publish = async () => {
    const savedId = save();
    if (!savedId) return;
    setNotice(null);
    setPublishing(true);
    try {
      recordAgentReview(savedId, await agentReviewListing(inputOf(form)));
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : UNEXPECTED_ERROR);
    } finally {
      setPublishing(false);
    }
  };

  // The corrected listing goes into the form, to finish (its gaps) and send again: nothing is saved yet.
  const useRewrite = (text: string) => {
    setForm((current) => ({ ...current, text }));
    setNotice(null);
  };

  const fillWith = (exampleId: string) => {
    const example = EXAMPLES.find((candidate) => candidate.id === exampleId);
    if (example) setForm(formOf(example.input));
    setNotice(null);
    setError(null);
  };

  const busy = checking || publishing;
  const unchanged = listing !== undefined && sameInput(inputOf(form), listing.input);
  const agentReview = listing?.lastReview === "agent" ? listing.agentReview : undefined;
  const quickReview = agentReview ? undefined : listing?.quickReview;
  const changedSinceCheck = (agentReview || quickReview) && !unchanged;
  // Sending an unchanged listing again would pay for the same answer.
  const alreadySent = unchanged && (listing?.status === "published" || listing?.status === "pending_moderation");

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
      <div className="min-w-0 space-y-6">
        <header className="space-y-3">
          {listing && (
            <p className="text-sm text-muted">
              <StatusBadge status={listing.status} />
            </p>
          )}
          <h1 className="text-4xl font-semibold tracking-tight">Publica tu anuncio</h1>
          <p className="text-lg text-muted">
            Escríbelo como lo publicarías y compruébalo antes: la revisión te dice qué falta o qué incumple la normativa,
            con la norma que lo respalda. Puedes comprobarlo tantas veces como quieras.
          </p>
        </header>

        <Field label="Rellenar con un ejemplo">
          {(fieldId) => (
            <select id={fieldId} value="" onChange={(event) => fillWith(event.target.value)} className={`${fieldClass} sm:w-fit`}>
              <option value="">Elige un anuncio de ejemplo…</option>
              {EXAMPLES.map((example) => (
                <option key={example.id} value={example.id}>
                  {example.label}
                </option>
              ))}
            </select>
          )}
        </Field>

        <form onSubmit={check} className="space-y-4">
          <fieldset disabled={busy} className="space-y-4">
            <Field label="Pega o escribe tu anuncio">
              {(fieldId) => (
                <textarea
                  id={fieldId}
                  value={form.text}
                  onChange={(event) => set("text")(event.target.value)}
                  rows={9}
                  maxLength={MAX_TEXT}
                  placeholder="Piso de 2 habitaciones en… Renta de … €/mes, qué incluye… Fianza de… Certificado energético…"
                  className={`${fieldClass} px-4 py-3 text-base leading-relaxed`}
                />
              )}
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Precio (€/mes)">
                {(fieldId) => (
                  <input id={fieldId} type="number" min={0} step={50} value={form.price} onChange={(event) => set("price")(event.target.value)} className={fieldClass} />
                )}
              </Field>
              <Field label="Superficie útil (m²)">
                {(fieldId) => (
                  <input id={fieldId} type="number" min={0} value={form.surface} onChange={(event) => set("surface")(event.target.value)} className={fieldClass} />
                )}
              </Field>
              <Field label="Habitaciones">
                {(fieldId) => (
                  <input id={fieldId} type="number" min={0} step={1} value={form.rooms} onChange={(event) => set("rooms")(event.target.value)} className={fieldClass} />
                )}
              </Field>
              <Field label="Municipio">
                {(fieldId) => (
                  <input id={fieldId} value={form.municipality} onChange={(event) => set("municipality")(event.target.value)} className={fieldClass} />
                )}
              </Field>
              <Field label="Calificación energética">
                {(fieldId) => (
                  <select id={fieldId} value={form.energyRating} onChange={(event) => set("energyRating")(event.target.value)} className={fieldClass}>
                    <option value="">Sin indicar</option>
                    {ENERGY_RATINGS.map((rating) => (
                      <option key={rating}>{rating}</option>
                    ))}
                  </select>
                )}
              </Field>
            </div>
          </fieldset>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={busy || alreadySent}
              onClick={() => void publish()}
              className="rounded-lg bg-ink px-5 py-3 text-sm font-medium text-white hover:bg-ink-soft disabled:opacity-60"
            >
              {publishing ? "Enviando…" : "Enviar a publicar"}
            </button>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg border border-line bg-canvas px-5 py-3 text-sm font-medium text-ink hover:border-ink-soft disabled:opacity-60"
            >
              {checking ? "Comprobando…" : "Comprobar anuncio"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={saveOnly}
              className="px-2 py-3 text-sm font-medium text-ink-soft hover:text-ink disabled:opacity-60"
            >
              Guardar borrador
            </button>
            {notice && (
              <p role="status" className="text-sm text-ok">
                {notice}{" "}
                <Link to="/mis-anuncios" className="font-medium underline-offset-2 hover:underline">
                  Ver mis anuncios
                </Link>
              </p>
            )}
          </div>
          <p className="text-xs text-muted">
            Comprobar es rápido y puedes repetirlo. Al enviar a publicar, un agente lo revisa a fondo (unos 15 segundos):
            lo publica, te pide cambios o, si duda, lo deja en manos del equipo de moderación.
          </p>
        </form>
      </div>

      <aside aria-label="Revisión" className="min-w-0 space-y-4 self-start rounded-2xl border border-line bg-canvas-soft p-5 lg:sticky lg:top-24">
        <h2 className="text-lg font-semibold tracking-tight">Revisión del anuncio</h2>
        <ServiceBanner />
        {error && (
          <p role="alert" className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
            {error}
          </p>
        )}
        {checking && (
          <p role="status" className="text-sm text-muted">
            Revisando el anuncio contra la normativa…
          </p>
        )}
        {publishing && (
          <p role="status" className="rounded-xl bg-canvas-sunken px-4 py-3 text-sm text-ink-soft">
            {AGENT_REVIEWING}
          </p>
        )}
        {!busy && listing && agentReview && <Outcome listing={listing} />}
        {changedSinceCheck && !busy && (
          <p className="rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">{CHANGED_SINCE_CHECK}</p>
        )}
        {!busy && agentReview && <AgentReviewResult review={agentReview} onUseRewrite={useRewrite} />}
        {!busy && quickReview && <ReviewResult review={quickReview} />}
        {!busy && !agentReview && !quickReview && (
          <p className="text-sm text-muted">
            Aquí verás el veredicto y cada incidencia, con su gravedad, qué hacer y la norma que la respalda.
          </p>
        )}
      </aside>
    </div>
  );
}
