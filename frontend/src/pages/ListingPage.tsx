import { useState } from "react";
import { Link, useParams } from "react-router";
import { findListing, type RentalListing } from "../catalogue/catalogue";
import { EnergyBadge } from "../components/EnergyBadge";
import { formatDate, formatNumber } from "../components/format";
import { ChevronLeftIcon, PinIcon } from "../components/icons";
import { AgencyBadge, FavouriteButton, KeyFact } from "../components/ListingCard";
import { PhotoGallery } from "../components/PhotoGallery";

export const LISTING_NOT_FOUND = "Este anuncio no existe o ya no está publicado.";

function ContactCard({ listing }: { listing: RentalListing }) {
  const [asked, setAsked] = useState(false);
  return (
    <aside className="space-y-4 self-start rounded-2xl border border-line bg-canvas p-5 shadow-sm lg:sticky lg:top-24">
      <p>
        <span className="text-3xl font-semibold tracking-tight">{formatNumber(listing.priceEurMonth)} €</span>
        <span className="text-muted"> /mes</span>
      </p>
      <AgencyBadge agency={listing.agency} />
      <button
        type="button"
        onClick={() => setAsked(true)}
        className="w-full rounded-lg bg-ink px-4 py-3 text-sm font-medium text-white hover:bg-ink-soft"
      >
        Contactar
      </button>
      {asked && (
        <p role="status" className="rounded-lg bg-canvas-sunken p-3 text-sm text-ink-soft">
          En esta demo no se envían mensajes: la agencia es ficticia.
        </p>
      )}
      <p className="text-xs text-muted">Publicado el {formatDate(listing.publishedAt)}</p>
    </aside>
  );
}

export function ListingPage() {
  const { id = "" } = useParams();
  const listing = findListing(id);

  if (!listing) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-24 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">{LISTING_NOT_FOUND}</h1>
        <Link
          to="/alquiler"
          className="mt-6 inline-block rounded-lg bg-ink px-5 py-3 text-sm font-medium text-white hover:bg-ink-soft"
        >
          Ver pisos en alquiler
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Link
        to={`/alquiler?municipio=${encodeURIComponent(listing.municipality)}`}
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"
      >
        <ChevronLeftIcon className="size-4" />
        Pisos en alquiler en {listing.municipality}
      </Link>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-8">
          <div className="relative overflow-hidden rounded-2xl">
            <PhotoGallery photos={listing.photos} title={listing.title} variant="detail" />
            <FavouriteButton className="absolute top-3 right-3" />
          </div>

          <header className="space-y-2">
            <p className="flex items-center gap-1 text-sm text-muted">
              <PinIcon className="size-4" />
              {listing.neighbourhood}, {listing.municipality} · {listing.region}
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-balance">{listing.title}</h1>
          </header>

          <dl className="grid grid-cols-2 gap-6 rounded-2xl border border-line p-5 sm:grid-cols-4">
            <KeyFact value={formatNumber(listing.priceEurMonth)} unit="€/mes" />
            <KeyFact value={formatNumber(listing.usableSurfaceM2)} unit="m² útiles" />
            <KeyFact value={formatNumber(listing.rooms)} unit={listing.rooms === 1 ? "habitación" : "habitaciones"} />
            <KeyFact value={formatNumber(listing.bathrooms)} unit={listing.bathrooms === 1 ? "baño" : "baños"} />
          </dl>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold tracking-tight">Descripción</h2>
            <p className="leading-relaxed whitespace-pre-line text-ink-soft">{listing.description}</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold tracking-tight">Características</h2>
            <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
              <div className="flex justify-between border-b border-line pb-2">
                <dt className="text-muted">Planta</dt>
                <dd>{listing.floor}</dd>
              </div>
              <div className="flex items-center justify-between border-b border-line pb-2">
                <dt className="text-muted">Certificado energético</dt>
                <dd>
                  <EnergyBadge rating={listing.energyRating} />
                </dd>
              </div>
            </dl>
            <ul className="flex flex-wrap gap-2" aria-label="Equipamiento">
              {listing.features.map((feature) => (
                <li key={feature} className="rounded-full bg-canvas-sunken px-3 py-1 text-sm text-ink-soft">
                  {feature}
                </li>
              ))}
            </ul>
          </section>
        </div>

        <ContactCard listing={listing} />
      </div>
    </div>
  );
}
