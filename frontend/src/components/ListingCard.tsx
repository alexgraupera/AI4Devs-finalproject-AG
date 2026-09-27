import { useState } from "react";
import { Link } from "react-router";
import type { RentalListing } from "../catalogue/catalogue";
import { EnergyBadge } from "./EnergyBadge";
import { formatNumber } from "./format";
import { HeartIcon, PinIcon } from "./icons";
import { PhotoGallery } from "./PhotoGallery";

export function AgencyBadge({ agency }: { agency: RentalListing["agency"] }) {
  return (
    <span className="flex items-center gap-2 text-sm text-ink-soft">
      <span className="grid size-8 place-items-center rounded-md border border-line bg-canvas-soft text-xs font-bold text-ink">
        {agency.initials}
      </span>
      {agency.name}
    </span>
  );
}

/** A heart that remembers nothing on purpose: favourites are not part of what this demo is about. */
export function FavouriteButton({ className = "" }: { className?: string }) {
  const [saved, setSaved] = useState(false);
  return (
    <button
      type="button"
      aria-pressed={saved}
      aria-label={saved ? "Quitar de favoritos" : "Guardar en favoritos"}
      onClick={() => setSaved((current) => !current)}
      className={`grid size-9 place-items-center rounded-full bg-white/90 shadow-md transition-colors hover:bg-white ${saved ? "text-accent" : "text-ink"} ${className}`}
    >
      <HeartIcon className="size-5" filled={saved} />
    </button>
  );
}

/** A figure over its unit, as the reference portal shows them; the unit is the term, so it comes first in the markup. */
export function KeyFact({ value, unit }: { value: string; unit: string }) {
  return (
    <div className="flex flex-col-reverse">
      <dt className="text-xs text-muted">{unit}</dt>
      <dd className="text-xl font-semibold tracking-tight text-ink">{value}</dd>
    </div>
  );
}

/** A search result laid out as the reference portal does: gallery on the left, key figures in large type. */
export function ListingCard({ listing }: { listing: RentalListing }) {
  return (
    <article className="overflow-hidden rounded-2xl border border-line bg-canvas shadow-sm transition-shadow hover:shadow-lg md:grid md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <div className="relative">
        <PhotoGallery photos={listing.photos} title={listing.title} className="h-full" />
        <FavouriteButton className="absolute top-3 right-3" />
      </div>
      <div className="flex flex-col gap-4 p-5">
        <div className="space-y-1">
          <p className="flex items-center gap-1 text-sm text-muted">
            <PinIcon className="size-4" />
            {listing.neighbourhood}, {listing.municipality}
          </p>
          <h2 className="text-lg leading-snug font-semibold text-ink">
            <Link to={`/alquiler/${listing.id}`} className="hover:text-accent-strong">
              {listing.title}
            </Link>
          </h2>
        </div>
        <dl className="flex gap-8">
          <KeyFact value={formatNumber(listing.priceEurMonth)} unit="€/mes" />
          <KeyFact value={formatNumber(listing.usableSurfaceM2)} unit="m²" />
          <KeyFact value={formatNumber(listing.rooms)} unit="hab." />
        </dl>
        <ul className="flex flex-wrap gap-2" aria-label="Características">
          {listing.features.slice(0, 4).map((feature) => (
            <li key={feature} className="rounded-full bg-canvas-sunken px-3 py-1 text-xs text-ink-soft">
              {feature}
            </li>
          ))}
        </ul>
        <div className="mt-auto flex items-center justify-between gap-4 border-t border-line pt-4">
          <AgencyBadge agency={listing.agency} />
          <span className="flex items-center gap-2 text-xs text-muted">
            Certificado energético
            <EnergyBadge rating={listing.energyRating} />
          </span>
        </div>
      </div>
    </article>
  );
}
