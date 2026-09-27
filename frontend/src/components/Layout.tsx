import { Link, NavLink, Outlet } from "react-router";
import { DoorIcon } from "./icons";

export const DEMO_NOTICE =
  "Demo: los anuncios, las agencias y las fotos son ficticios. Las revisiones y las respuestas las genera el sistema de verdad.";

export function Logo({ inverted = false }: { inverted?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <span className="grid size-8 place-items-center rounded-lg bg-accent text-white">
        <DoorIcon className="size-5" />
      </span>
      <span className={`text-lg font-semibold tracking-tight ${inverted ? "text-white" : "text-ink"}`}>Umbral</span>
    </span>
  );
}

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm transition-colors ${isActive ? "text-ink font-semibold" : "text-ink-soft hover:text-ink"}`;

function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link to="/" aria-label="Umbral, inicio">
          <Logo />
        </Link>
        <nav aria-label="Principal" className="flex items-center gap-1">
          <NavLink to="/alquiler" className={navLinkClass}>
            Alquilar
          </NavLink>
          <Link to="/#como-funciona" className="hidden rounded-md px-3 py-2 text-sm text-ink-soft hover:text-ink sm:block">
            Cómo funciona
          </Link>
        </nav>
        <Link
          to="/alquiler"
          className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-ink-soft"
        >
          Buscar piso
        </Link>
      </div>
    </header>
  );
}

const FOOTER_MUNICIPALITIES = ["Palma", "Barcelona", "Madrid", "Valencia", "Sevilla", "Bilbao"];

function Footer() {
  return (
    <footer className="border-t border-line bg-canvas-soft">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:grid-cols-3">
        <div className="space-y-3">
          <Logo />
          <p className="text-sm text-muted">Alquila sin sorpresas.</p>
        </div>
        <nav aria-label="Alquilar por municipio" className="space-y-3">
          <h2 className="text-sm font-semibold">Alquilar</h2>
          <ul className="grid grid-cols-2 gap-2 text-sm text-ink-soft">
            {FOOTER_MUNICIPALITIES.map((municipality) => (
              <li key={municipality}>
                <Link to={`/alquiler?municipio=${encodeURIComponent(municipality)}`} className="hover:text-ink">
                  Pisos en {municipality}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="space-y-3 text-sm text-ink-soft">
          <h2 className="font-semibold text-ink">Sobre esta demo</h2>
          <p>Proyecto final del máster AI4Devs de LIDR: un marketplace de alquiler ficticio sobre un servicio de IA real.</p>
          <p>
            Fotos de dominio público (CC0).{" "}
            <a href="/photos/CREDITS.md" className="text-accent-strong underline-offset-2 hover:underline">
              Créditos
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col font-sans">
      <p className="bg-accent-soft px-4 py-2 text-center text-xs text-accent-strong">{DEMO_NOTICE}</p>
      <Header />
      <main className="flex flex-1 flex-col">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
