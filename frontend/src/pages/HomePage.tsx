import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { municipalities, placeOf, searchListings, type RentalListing } from "../catalogue/catalogue";
import { formatNumber } from "../components/format";
import { ArrowRightIcon, CheckIcon, PauseIcon, PinIcon, ScaleIcon, SearchIcon } from "../components/icons";

const POPULAR = ["Palma", "Barcelona", "Madrid", "Valencia"];

function Hero() {
  const navigate = useNavigate();
  const [municipality, setMunicipality] = useState("");

  const search = (event: FormEvent) => {
    event.preventDefault();
    const typed = municipality.trim();
    navigate(typed ? `/alquiler?municipio=${encodeURIComponent(typed)}` : "/alquiler");
  };

  return (
    <section className="bg-linear-to-b from-canvas to-canvas-soft">
      <div className="mx-auto max-w-6xl px-4 pt-20 pb-20 text-center sm:pt-28">
        <span className="inline-flex items-center gap-2 rounded-full border border-accent-line bg-accent-soft px-3 py-1 text-xs font-medium text-accent-strong">
          <ScaleIcon className="size-4" />
          Anuncios revisados contra la normativa del BOE
        </span>
        <h1 className="mx-auto mt-6 max-w-3xl pb-2 text-5xl font-semibold tracking-tighter text-balance sm:text-7xl">
          Alquila{" "}
          <span className="bg-linear-to-r from-accent-strong to-accent bg-clip-text text-transparent">sin sorpresas</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-balance text-muted">
          Pisos de alquiler cuyos anuncios revisa una IA antes de publicarse, y respuestas sobre tus derechos con el
          artículo de la ley del que salen.
        </p>

        <form
          role="search"
          onSubmit={search}
          className="mx-auto mt-10 flex max-w-xl items-center gap-2 rounded-2xl border border-line bg-canvas p-2 shadow-xl"
        >
          <SearchIcon className="ml-3 size-5 shrink-0 text-muted" />
          <label htmlFor="home-municipality" className="sr-only">
            Municipio
          </label>
          <input
            id="home-municipality"
            list="home-municipalities"
            value={municipality}
            onChange={(event) => setMunicipality(event.target.value)}
            placeholder="¿Dónde quieres vivir?"
            className="min-w-0 flex-1 bg-transparent py-2 text-base outline-none placeholder:text-muted"
          />
          <datalist id="home-municipalities">
            {municipalities().map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <button type="submit" className="rounded-xl bg-ink px-5 py-3 text-sm font-medium text-white shadow-sm hover:bg-ink-soft">
            Buscar piso
          </button>
        </form>

        <p className="mt-5 flex flex-wrap items-center justify-center gap-2 text-sm text-muted">
          Populares:
          {POPULAR.map((name) => (
            <Link
              key={name}
              to={`/alquiler?municipio=${encodeURIComponent(name)}`}
              className="rounded-full border border-line bg-canvas px-3 py-1 text-ink-soft hover:border-ink-soft hover:text-ink"
            >
              {name}
            </Link>
          ))}
        </p>

        <p className="mt-6 text-sm text-muted">
          ¿Tienes un piso para alquilar?{" "}
          <Link to="/publicar" className="font-medium text-accent-strong underline-offset-2 hover:underline">
            Publicar anuncio
          </Link>
        </p>
      </div>
    </section>
  );
}

function CompactCard({ listing }: { listing: RentalListing }) {
  return (
    <article className="group overflow-hidden rounded-2xl border border-line bg-canvas shadow-sm transition-shadow hover:shadow-lg">
      <img src={listing.photos[0]} alt="" loading="lazy" className="aspect-[4/3] w-full object-cover" />
      <div className="space-y-2 p-4">
        <p className="text-lg font-semibold tracking-tight">
          {formatNumber(listing.priceEurMonth)} € <span className="text-sm font-normal text-muted">/mes</span>
        </p>
        <h3 className="leading-snug font-medium">
          <Link to={`/alquiler/${listing.id}`} className="hover:text-accent-strong">
            {listing.title}
          </Link>
        </h3>
        <p className="flex items-center gap-1 text-sm text-muted">
          <PinIcon className="size-4" />
          {[placeOf(listing), listing.usableSurfaceM2 > 0 && `${listing.usableSurfaceM2} m²`, listing.rooms > 0 && `${listing.rooms} hab.`]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>
    </article>
  );
}

function Latest() {
  const latest = searchListings({}, "recent").slice(0, 3);
  return (
    <section className="mx-auto max-w-6xl px-4 py-20">
      <div className="mb-8 flex items-end justify-between gap-4">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Recién publicados</h2>
        <Link to="/alquiler" className="flex shrink-0 items-center gap-1 text-sm font-medium whitespace-nowrap text-accent-strong hover:underline">
          Ver todos los pisos
          <ArrowRightIcon className="size-4" />
        </Link>
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        {latest.map((listing) => (
          <CompactCard key={listing.id} listing={listing} />
        ))}
      </div>
    </section>
  );
}

type ToolSectionProps = {
  eyebrow: string;
  title: string;
  children: ReactNode;
  facts: string[];
  preview: ReactNode;
  reversed?: boolean;
  action?: { to: string; label: string };
};

function ToolSection({ eyebrow, title, children, facts, preview, reversed = false, action }: ToolSectionProps) {
  return (
    <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
      <div className={`space-y-5 ${reversed ? "lg:order-2" : ""}`}>
        <p className="text-sm font-semibold tracking-wide text-accent-strong uppercase">{eyebrow}</p>
        <h3 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{title}</h3>
        <div className="space-y-3 text-lg text-muted">{children}</div>
        <ul className="flex flex-wrap gap-2">
          {facts.map((fact) => (
            <li key={fact} className="rounded-full border border-line bg-canvas px-3 py-1 text-sm text-ink-soft">
              {fact}
            </li>
          ))}
        </ul>
        {action && (
          <Link
            to={action.to}
            className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-soft"
          >
            {action.label}
            <ArrowRightIcon className="size-4" />
          </Link>
        )}
      </div>
      {preview}
    </div>
  );
}

/** A dark panel that previews a tool, as the reference shows its product: an example, labelled as one. */
function PreviewPanel({ label, children }: { label: string; children: ReactNode }) {
  return (
    <figure className="rounded-3xl bg-panel p-3 shadow-xl">
      <div className="flex items-center gap-1.5 px-3 pt-1 pb-3">
        <span className="size-2.5 rounded-full bg-panel-line" />
        <span className="size-2.5 rounded-full bg-panel-line" />
        <span className="size-2.5 rounded-full bg-panel-line" />
        <figcaption className="ml-3 text-xs text-panel-muted">{label}</figcaption>
      </div>
      <div className="space-y-3 rounded-2xl bg-panel-raised p-5 text-sm text-panel-text">{children}</div>
    </figure>
  );
}

function RightsPreview() {
  return (
    <PreviewPanel label="Ejemplo · Tus derechos sobre este anuncio">
      <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-4 py-2 text-ink">
        ¿Me pueden pedir dos meses de fianza?
      </p>
      <div className="max-w-[92%] space-y-3 rounded-2xl rounded-bl-sm border border-panel-line p-4">
        <p>
          No. En el alquiler de vivienda la fianza es de una mensualidad de renta. Aparte se pueden pactar garantías
          adicionales, que no pueden superar dos mensualidades.
        </p>
        <p className="text-xs text-panel-muted">Fuentes</p>
        <ul className="flex flex-wrap gap-2 text-xs">
          <li className="rounded-full border border-panel-line px-2.5 py-1">Ley de Arrendamientos Urbanos · Artículo 36</li>
        </ul>
      </div>
    </PreviewPanel>
  );
}

function CheckPreview() {
  return (
    <PreviewPanel label="Ejemplo · Comprobar anuncio">
      <p className="flex items-center justify-between">
        <span className="font-semibold">Revisión del anuncio</span>
        <span className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-semibold text-ink">Requiere cambios</span>
      </p>
      <ul className="space-y-2">
        {[
          ["Alta", "La fianza de dos mensualidades supera la legal", "LAU art. 36.1"],
          ["Alta", "Los honorarios de la agencia no pueden cobrarse al inquilino", "LAU art. 20.1"],
          ["Media", "Falta la calificación energética", "RD 390/2021 art. 15.2"],
        ].map(([severity, message, basis]) => (
          <li key={message} className="rounded-xl border border-panel-line p-3">
            <p>
              <span className="mr-2 text-xs font-semibold text-accent">{severity}</span>
              {message}
            </p>
            <p className="mt-1 text-xs text-panel-muted">Base legal: {basis}</p>
          </li>
        ))}
      </ul>
    </PreviewPanel>
  );
}

function AgentPreview() {
  const steps: [string, string, boolean][] = [
    ["Comprobar los datos del anuncio", "Precio, superficie y certificado", true],
    ["Consultar la normativa", "LAU art. 36 · Ley 12/2023 art. 31", true],
    ["Entregar la revisión", "3 incidencias con su artículo", true],
    ["Revisor", "Pone en duda 1 incidencia", true],
    ["Espera a una persona", "El equipo de moderación decide", false],
  ];
  return (
    <PreviewPanel label="Ejemplo · Pasos del agente">
      <ol className="space-y-2">
        {steps.map(([title, detail, done], position) => (
          <li key={title} className="flex items-start gap-3 rounded-xl border border-panel-line p-3">
            <span
              className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ${done ? "bg-panel-line text-panel-text" : "bg-accent text-ink"}`}
            >
              {done ? <CheckIcon className="size-4" /> : <PauseIcon className="size-4" />}
            </span>
            <span>
              <span className="font-medium">
                {position + 1}. {title}
              </span>
              <span className="block text-xs text-panel-muted">{detail}</span>
            </span>
          </li>
        ))}
      </ol>
    </PreviewPanel>
  );
}

function Tools() {
  return (
    <section id="herramientas" className="border-y border-line bg-canvas-soft">
      <div className="mx-auto max-w-6xl space-y-24 px-4 py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-5xl">La letra pequeña, revisada antes de que la leas</h2>
          <p className="mt-4 text-lg text-muted">
            Tres herramientas de IA sobre la normativa de alquiler, cada una donde hace falta: al buscar, al redactar y al
            publicar.
          </p>
        </div>
        <ToolSection
          eyebrow="Para inquilinos"
          title="Tus derechos, con el artículo que los respalda"
          facts={["Ley de Arrendamientos Urbanos", "Ley de vivienda", "Normativa catalana"]}
          preview={<RightsPreview />}
          action={{ to: "/normativa", label: "Pregunta a la normativa" }}
        >
          <p>
            Pregunta desde cualquier anuncio si te pueden pedir dos meses de fianza o cobrarte los honorarios. La respuesta
            sale solo de la normativa publicada en el BOE y enlaza el artículo; si la normativa no lo cubre, te dice que no
            lo sabe.
          </p>
        </ToolSection>
        <ToolSection
          eyebrow="Para anunciantes"
          title="Comprueba tu anuncio antes de publicarlo"
          facts={["Unos 3 segundos", "Menos de medio céntimo por revisión"]}
          preview={<CheckPreview />}
          action={{ to: "/publicar", label: "Comprueba tu anuncio" }}
          reversed
        >
          <p>
            Pega tu anuncio y sabrás qué falta o qué incumple la normativa: la fianza, los honorarios, el certificado
            energético, los gastos. Cada incidencia llega con su gravedad, una sugerencia concreta y la norma que la
            respalda.
          </p>
        </ToolSection>
        <ToolSection
          eyebrow="Al publicar"
          title="Un agente revisa y corrige; si duda, decide una persona"
          facts={["Cita cada artículo", "Propone el anuncio corregido", "Una persona decide cuando duda"]}
          preview={<AgentPreview />}
        >
          <p>
            Antes de publicar, un agente consulta la normativa, cita el artículo de cada incidencia y propone el anuncio
            corregido. Un segundo modelo comprueba sus conclusiones: si no puede respaldarlas, el anuncio espera a que el
            equipo de moderación decida.
          </p>
        </ToolSection>
      </div>
    </section>
  );
}

const STEPS = [
  ["Buscas o publicas", "Como en cualquier portal: filtros, fotos y fichas; o tu anuncio, con sus datos."],
  ["La IA lo revisa con la ley", "Contra la Ley de Arrendamientos Urbanos, la Ley de vivienda y la normativa catalana."],
  ["Una persona decide si duda", "Lo que la IA no puede respaldar no se publica solo: lo revisa el equipo."],
  ["Tú tienes la última palabra", "Cada incidencia y cada respuesta enlazan el artículo, para que lo compruebes."],
];

function HowItWorks() {
  return (
    <section id="como-funciona" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24">
      <h2 className="text-3xl font-semibold tracking-tight sm:text-5xl">Cómo funciona</h2>
      <ol className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(([title, text], position) => (
          <li key={title} className="rounded-2xl border border-line p-6">
            <span className="grid size-9 place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent-strong">
              {position + 1}
            </span>
            <h3 className="mt-4 font-semibold">{title}</h3>
            <p className="mt-2 text-sm text-muted">{text}</p>
          </li>
        ))}
      </ol>
      <p className="mt-8 rounded-2xl bg-canvas-sunken p-5 text-sm text-ink-soft">
        <span className="font-semibold text-ink">Por dentro:</span> este marketplace es ficticio; el servicio de IA que
        lo revisa todo es real. Un servidor propio guarda las credenciales y llama a una API en FastAPI que combina el
        checklist legal en el prompt (CAG), la búsqueda sobre la normativa del BOE con pgvector (RAG) y un agente con
        revisor y pausa para una persona.
      </p>
    </section>
  );
}

const FAQ = [
  [
    "¿Son reales los anuncios?",
    "No. Los anuncios, las agencias y las direcciones son ficticios, y las fotos son de dominio público, no de los pisos descritos. Lo que sí es real es la IA: cada revisión y cada respuesta se generan en el momento.",
  ],
  [
    "¿Es asesoramiento legal?",
    "No. Las respuestas salen de la normativa indexada y citan el artículo del que proceden para que puedas comprobarlas, pero no sustituyen a un profesional.",
  ],
  [
    "¿Qué normativa cubre?",
    "La Ley de Arrendamientos Urbanos, la Ley 12/2023 por el derecho a la vivienda, el Real Decreto 390/2021 sobre certificación energética, la Ley 18/2007 del derecho a la vivienda de Cataluña y las resoluciones de zonas tensionadas publicadas en el BOE. Sobre fiscalidad, comunidades de propietarios o desahucios dirá que no lo sabe.",
  ],
  [
    "¿Por qué a veces un anuncio espera a una persona?",
    "Porque un segundo modelo comprueba cada conclusión del agente contra el anuncio y el artículo citado. Cuando no puede respaldarla, la revisión se pausa y el equipo de moderación decide si se mantiene, se ajusta o se descarta.",
  ],
  [
    "¿Cuánto cuesta cada revisión?",
    "Comprobar un anuncio cuesta unos 0,004 $ y tarda unos 3 segundos. La revisión del agente al publicar cuesta unos 0,025 $ y tarda unos 15 segundos: es más cara, y también la que mejor resultado da en la evaluación.",
  ],
];

function Faq() {
  return (
    <section id="preguntas" className="mx-auto max-w-3xl scroll-mt-20 px-4 pb-24">
      <h2 className="text-center text-3xl font-semibold tracking-tight sm:text-5xl">Preguntas frecuentes</h2>
      <div className="mt-10 divide-y divide-line rounded-2xl border border-line">
        {FAQ.map(([question, answer]) => (
          <details key={question} className="group p-5">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
              {question}
              <span className="text-xl text-muted transition-transform group-open:rotate-45" aria-hidden="true">
                +
              </span>
            </summary>
            <p className="mt-3 text-ink-soft">{answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function ClosingCta() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-24">
      <div className="rounded-3xl bg-panel px-6 py-16 text-center">
        <h2 className="text-3xl font-semibold tracking-tight text-balance text-panel-text sm:text-4xl">
          Tu próximo piso, sin letra pequeña
        </h2>
        <Link
          to="/alquiler"
          className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-medium text-ink hover:bg-canvas-sunken"
        >
          Buscar piso
          <ArrowRightIcon className="size-4" />
        </Link>
      </div>
    </section>
  );
}

export function HomePage() {
  return (
    <div>
      <Hero />
      <Latest />
      <Tools />
      <HowItWorks />
      <Faq />
      <ClosingCta />
    </div>
  );
}
