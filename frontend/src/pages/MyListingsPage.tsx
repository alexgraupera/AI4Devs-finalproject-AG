import { Link } from "react-router";
import { formatNumber } from "../components/format";
import { VerdictBadge } from "../components/ReviewResult";
import { STATUS_LABELS } from "../landlord/labels";
import { useMyListings, type MyListing } from "../landlord/myListingsStore";

export const NO_LISTINGS = "Aún no tienes anuncios. Publica el primero.";

const DATE_TIME = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** A listing has no title of its own: its first sentence is what the landlord recognises it by. */
function titleOf(listing: MyListing): string {
  const firstSentence = listing.input.text.split(/(?<=\.)\s/)[0];
  return firstSentence.length > 90 ? `${firstSentence.slice(0, 87)}…` : firstSentence;
}

function factsOf(listing: MyListing): string {
  const { municipality, price_eur_month, usable_surface_m2, rooms } = listing.input;
  return [
    municipality,
    price_eur_month !== null && `${formatNumber(price_eur_month)} €/mes`,
    usable_surface_m2 !== null && `${formatNumber(usable_surface_m2)} m²`,
    rooms !== null && `${rooms} hab.`,
  ]
    .filter(Boolean)
    .join(" · ");
}

function MyListingCard({ listing }: { listing: MyListing }) {
  const review = listing.quickReview;
  return (
    <article className="flex flex-col gap-4 rounded-2xl border border-line bg-canvas p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 space-y-2">
        <p className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-canvas-sunken px-2.5 py-1 text-xs font-medium text-ink-soft">
            {STATUS_LABELS[listing.status]}
          </span>
          <span className="text-xs text-muted">Actualizado el {DATE_TIME.format(new Date(listing.updatedAt))}</span>
        </p>
        <h2 className="font-semibold leading-snug">
          <Link to={`/publicar/${listing.id}`} className="hover:text-accent-strong">
            {titleOf(listing)}
          </Link>
        </h2>
        {factsOf(listing) && <p className="text-sm text-muted">{factsOf(listing)}</p>}
        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-soft">
          {review ? (
            <>
              Última comprobación: <VerdictBadge verdict={review.verdict} />
              {review.findings.length > 0 && <span className="text-muted">{review.findings.length} incidencias</span>}
            </>
          ) : (
            <span className="text-muted">Sin comprobar todavía</span>
          )}
        </div>
      </div>
      <Link
        to={`/publicar/${listing.id}`}
        className="shrink-0 rounded-lg border border-line px-4 py-2 text-center text-sm font-medium hover:border-ink-soft"
      >
        Editar
      </Link>
    </article>
  );
}

/** The landlord's listings, newest change first, with where each one is on its way to publication. */
export function MyListingsPage() {
  const listings = [...useMyListings()].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-4xl font-semibold tracking-tight">Mis anuncios</h1>
          <p className="text-muted">Se guardan en este navegador: la demo no tiene cuentas de usuario.</p>
        </div>
        <Link to="/publicar" className="rounded-lg bg-ink px-5 py-3 text-sm font-medium text-white hover:bg-ink-soft">
          Publicar anuncio
        </Link>
      </header>
      {listings.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-line px-6 py-16 text-center text-ink-soft">{NO_LISTINGS}</p>
      ) : (
        <ol aria-label="Mis anuncios" className="space-y-4">
          {listings.map((listing) => (
            <li key={listing.id}>
              <MyListingCard listing={listing} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
