import { useEffect, useEffectEvent, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { SIGN_IN_REQUIRED_EVENT, signOut } from "../api/client";
import { markSignedIn, useSession } from "../api/sessionStore";
import { pendingModeration, useMyListings } from "../landlord/myListingsStore";
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

const NAV = [
  { to: "/alquiler", label: "Alquilar" },
  { to: "/normativa", label: "Normativa" },
  { to: "/mis-anuncios", label: "Mis anuncios" },
];

/** The quality team's queue, with how many reviews wait in it: the other side of the same marketplace. */
function ModerationLink({ className }: { className: (state: { isActive: boolean }) => string }) {
  const waiting = pendingModeration(useMyListings()).length;
  return (
    <NavLink to="/moderacion" className={className}>
      Moderación
      <span className="ml-1.5 rounded bg-panel px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-panel-text uppercase">
        Equipo
      </span>
      {waiting > 0 && (
        <span
          aria-label={`${waiting} pendientes`}
          className="ml-1 rounded-full bg-accent px-1.5 py-0.5 text-[10px] font-bold text-ink"
        >
          {waiting}
        </span>
      )}
    </NavLink>
  );
}

const linkState = (isActive: boolean) => (isActive ? "text-ink font-semibold" : "text-ink-soft hover:text-ink");
const navLinkClass = ({ isActive }: { isActive: boolean }) => `rounded-md px-3 py-2 text-sm transition-colors ${linkState(isActive)}`;
// Larger on a phone: a finger needs more room than a pointer.
const menuLinkClass = ({ isActive }: { isActive: boolean }) => `block rounded-md px-3 py-3 text-base ${linkState(isActive)}`;

const primaryButtonClass =
  "rounded-lg bg-ink px-4 py-2 text-sm font-medium whitespace-nowrap text-white shadow-sm transition-colors hover:bg-ink-soft";

/** A tool call the web server refused for lack of a session: to the login, and back here afterwards. */
function SignInRedirect() {
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  // The router's own location, always the current one: the browser's matches it in the app, and a
  // test's memory router has only this one.
  const toSignIn = useEffectEvent(() => {
    markSignedIn(false);
    navigate(`/acceso?volver=${encodeURIComponent(`${pathname}${search}`)}`);
  });
  useEffect(() => {
    const onRequired = () => toSignIn();
    window.addEventListener(SIGN_IN_REQUIRED_EVENT, onRequired);
    return () => window.removeEventListener(SIGN_IN_REQUIRED_EVENT, onRequired);
  }, []);
  return null;
}

/** "Acceder" or "Cerrar sesión", when the demo asks for its login at all. */
function Account({ className }: { className: string }) {
  const current = useSession();
  const { pathname, search } = useLocation();
  if (!current?.login_required) return null;
  if (!current.signed_in) {
    const here = pathname === "/acceso" ? "/" : `${pathname}${search}`;
    return (
      <Link to={`/acceso?volver=${encodeURIComponent(here)}`} className={className}>
        Acceder
      </Link>
    );
  }
  return (
    <button
      type="button"
      className={className}
      onClick={async () => {
        await signOut().catch(() => undefined);
        markSignedIn(false);
      }}
    >
      Cerrar sesión
    </button>
  );
}

/** On a phone the links do not fit in one row: they go behind a menu button, closed on every navigation. */
function MobileMenu() {
  const { pathname, hash } = useLocation();
  const [open, setOpen] = useState(false);
  const [openedAt, setOpenedAt] = useState(`${pathname}${hash}`);
  if (open && openedAt !== `${pathname}${hash}`) {
    setOpen(false);
    setOpenedAt(`${pathname}${hash}`);
  }

  return (
    <div className="md:hidden">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="mobile-menu"
        onClick={() => {
          setOpen((current) => !current);
          setOpenedAt(`${pathname}${hash}`);
        }}
        className="rounded-lg border border-line px-3 py-2 text-sm font-medium"
      >
        Menú
      </button>
      {open && (
        <nav id="mobile-menu" aria-label="Menú" className="absolute inset-x-0 top-16 border-b border-line bg-canvas px-4 py-3 shadow-lg">
          <ul className="flex flex-col">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} className={menuLinkClass}>
                  {item.label}
                </NavLink>
              </li>
            ))}
            <li>
              <ModerationLink className={menuLinkClass} />
            </li>
            <li>
              <Account className={`w-full text-left ${menuLinkClass({ isActive: false })}`} />
            </li>
            <li>
              <Link to="/#como-funciona" className={menuLinkClass({ isActive: false })}>
                Cómo funciona
              </Link>
            </li>
            <li className="pt-2">
              <Link to="/publicar" className="block rounded-lg bg-ink px-4 py-3 text-center text-base font-medium text-white">
                Publicar anuncio
              </Link>
            </li>
          </ul>
        </nav>
      )}
    </div>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
      <div className="relative mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link to="/" aria-label="Umbral, inicio">
          <Logo />
        </Link>
        <nav aria-label="Principal" className="hidden items-center gap-1 md:flex">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={navLinkClass}>
              {item.label}
            </NavLink>
          ))}
          <ModerationLink className={navLinkClass} />
          {/* Not enough room for it next to the rest until the header is wide; the landing links to it. */}
          <Link to="/#como-funciona" className="hidden rounded-md px-3 py-2 text-sm text-ink-soft hover:text-ink lg:block">
            Cómo funciona
          </Link>
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          <Account className="rounded-md px-3 py-2 text-sm whitespace-nowrap text-ink-soft hover:text-ink" />
          <Link to="/publicar" className={primaryButtonClass}>
            Publicar anuncio
          </Link>
        </div>
        <MobileMenu />
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
      <SignInRedirect />
      <Header />
      <main className="flex flex-1 flex-col">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
