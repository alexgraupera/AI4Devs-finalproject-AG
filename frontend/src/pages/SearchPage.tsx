import { Link, useSearchParams } from "react-router";
import { municipalities, searchListings, type SearchFilters, type SortOrder } from "../catalogue/catalogue";
import { formatNumber } from "../components/format";
import { ListingCard } from "../components/ListingCard";

/**
 * The results page. The filters live in the URL (in Spanish, as the rest of the site), so a search can
 * be shared, reloaded or reached from the landing and the footer with a plain link.
 */

const SORT_PARAMS: Record<string, SortOrder> = {
  recientes: "recent",
  "precio-asc": "price_asc",
  "precio-desc": "price_desc",
  superficie: "surface_desc",
};

const SORT_LABELS: Record<string, string> = {
  recientes: "Más recientes",
  "precio-asc": "Precio más bajo",
  "precio-desc": "Precio más alto",
  superficie: "Más superficie",
};

const PRICE_OPTIONS = [800, 1000, 1200, 1500, 2000, 2500];
const ROOM_OPTIONS = [1, 2, 3, 4];
const SURFACE_OPTIONS = [50, 70, 90, 110];

const FILTER_PARAMS = ["municipio", "precio_max", "habitaciones", "superficie_min"] as const;

function numberParam(value: string | null): number | undefined {
  if (!value) return undefined;
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function resultsHeading(count: number, municipality?: string): string {
  const flats = count === 1 ? "piso en alquiler" : "pisos en alquiler";
  return `${formatNumber(count)} ${flats}${municipality ? ` en ${municipality}` : ""}`;
}

type FilterSelectProps = {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
};

function FilterSelect({ label, name, value, onChange, options }: FilterSelectProps) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs font-medium text-muted">
      {label}
      <select
        name={name}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg border border-line bg-canvas px-3 py-2 text-sm font-normal text-ink focus:border-accent"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SearchPage() {
  const [params, setParams] = useSearchParams();

  // "malaga" typed on the landing is shown as "Málaga": the name the listings use.
  const municipalityOptions = municipalities();
  const typed = params.get("municipio")?.trim() || undefined;
  const municipality =
    typed && (municipalityOptions.find((name) => name.localeCompare(typed, "es", { sensitivity: "base" }) === 0) ?? typed);
  // One with no listings is still shown as the one searched, with the empty state below.
  if (municipality && !municipalityOptions.includes(municipality)) municipalityOptions.unshift(municipality);

  const filters: SearchFilters = {
    municipality,
    maxPrice: numberParam(params.get("precio_max")),
    minRooms: numberParam(params.get("habitaciones")),
    minSurface: numberParam(params.get("superficie_min")),
  };
  const sortParam = params.get("orden") ?? "recientes";
  const results = searchListings(filters, SORT_PARAMS[sortParam] ?? "recent");
  const hasFilters = FILTER_PARAMS.some((name) => params.get(name));

  const setParam = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    setParams(next);
  };

  const clearFilters = () => {
    const next = new URLSearchParams(params);
    FILTER_PARAMS.forEach((name) => next.delete(name));
    setParams(next);
  };

  return (
    <div className="flex-1 bg-canvas-soft">
      <div className="mx-auto max-w-6xl px-4 py-8">
        <nav aria-label="Migas de pan" className="mb-4 text-sm text-muted">
          <Link to="/" className="hover:text-ink">
            Inicio
          </Link>{" "}
          / <span className="text-ink-soft">Alquiler{municipality ? ` en ${municipality}` : ""}</span>
        </nav>

        <section
          aria-label="Filtros"
          className="mb-6 flex flex-col gap-3 rounded-2xl border border-line bg-canvas p-4 shadow-sm sm:flex-row sm:items-end"
        >
          <FilterSelect
            label="Municipio"
            name="municipio"
            value={municipality ?? ""}
            onChange={(value) => setParam("municipio", value)}
            options={[{ value: "", label: "Toda España" }, ...municipalityOptions.map((name) => ({ value: name, label: name }))]}
          />
          <FilterSelect
            label="Precio hasta"
            name="precio_max"
            value={params.get("precio_max") ?? ""}
            onChange={(value) => setParam("precio_max", value)}
            options={[
              { value: "", label: "Sin límite" },
              ...PRICE_OPTIONS.map((price) => ({ value: `${price}`, label: `${formatNumber(price)} €/mes` })),
            ]}
          />
          <FilterSelect
            label="Habitaciones"
            name="habitaciones"
            value={params.get("habitaciones") ?? ""}
            onChange={(value) => setParam("habitaciones", value)}
            options={[{ value: "", label: "Todas" }, ...ROOM_OPTIONS.map((rooms) => ({ value: `${rooms}`, label: `${rooms} o más` }))]}
          />
          <FilterSelect
            label="Superficie desde"
            name="superficie_min"
            value={params.get("superficie_min") ?? ""}
            onChange={(value) => setParam("superficie_min", value)}
            options={[{ value: "", label: "Sin mínimo" }, ...SURFACE_OPTIONS.map((surface) => ({ value: `${surface}`, label: `${surface} m²` }))]}
          />
          {hasFilters && (
            <button type="button" onClick={clearFilters} className="px-2 py-2 text-sm font-medium text-accent-strong hover:underline">
              Borrar filtros
            </button>
          )}
        </section>

        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">{resultsHeading(results.length, municipality)}</h1>
          <label className="flex items-center gap-2 text-sm text-muted">
            Ordenar por
            <select
              name="orden"
              value={SORT_PARAMS[sortParam] ? sortParam : "recientes"}
              onChange={(event) => setParam("orden", event.target.value === "recientes" ? "" : event.target.value)}
              className="rounded-lg border border-line bg-canvas px-3 py-2 text-sm text-ink"
            >
              {Object.entries(SORT_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {results.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-line bg-canvas px-6 py-16 text-center">
            <p className="text-ink-soft">No hay pisos con estos filtros. Prueba a quitar alguno.</p>
            {hasFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="mt-4 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-ink-soft"
              >
                Borrar filtros
              </button>
            )}
          </div>
        ) : (
          <ol className="space-y-5" aria-label="Resultados">
            {results.map((listing) => (
              <li key={listing.id}>
                <ListingCard listing={listing} />
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
