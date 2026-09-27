import type { EnergyRating } from "../catalogue/catalogue";

const SCALE: Record<Exclude<EnergyRating, "En trámite" | "Exenta">, string> = {
  A: "bg-energy-a",
  B: "bg-energy-b",
  C: "bg-energy-c",
  D: "bg-energy-d",
  E: "bg-energy-e",
  F: "bg-energy-f",
  G: "bg-energy-g",
};

/** The letter on the EU scale colour; a rating in progress or missing is said in words, never coloured. */
export function EnergyBadge({ rating }: { rating: EnergyRating | null }) {
  if (rating === null) {
    return <span className="rounded-md bg-canvas-sunken px-2 py-0.5 text-xs font-medium text-muted">Sin calificación</span>;
  }
  if (rating === "En trámite" || rating === "Exenta") {
    return <span className="rounded-md bg-canvas-sunken px-2 py-0.5 text-xs font-medium text-ink-soft">{rating}</span>;
  }
  return (
    <span className={`inline-grid min-w-6 place-items-center rounded-md px-1.5 py-0.5 text-xs font-bold text-ink ${SCALE[rating]}`}>
      {rating}
    </span>
  );
}
