import { useId, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ApiError, signIn, UNEXPECTED_ERROR } from "../api/client";
import { markSignedIn, useSession } from "../api/sessionStore";

export const LOGIN_TITLE = "Acceso a la demo";
export const SIGN_IN_TO_USE = "Inicia sesión para usar las herramientas.";

/** Only a page of this site: `?volver=//elsewhere.example` must not turn the login into a redirect out. */
function safeReturn(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.startsWith("/\\") ? value : "/";
}

const fieldClass = "w-full rounded-lg border border-line bg-canvas px-3 py-2.5 text-sm text-ink";

/**
 * The demo's shared login (ADR 0034, now in the web server). A tool call without a session lands here,
 * and signing in goes back to the page that asked.
 */
export function LoginPage() {
  const [params] = useSearchParams();
  const returnTo = safeReturn(params.get("volver"));
  const navigate = useNavigate();
  const current = useSession();
  const userId = useId();
  const passwordId = useId();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSending(true);
    setError(null);
    try {
      await signIn(username, password);
      markSignedIn(true);
      navigate(returnTo, { replace: true });
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : UNEXPECTED_ERROR);
      setSending(false);
    }
  };

  return (
    <div className="flex flex-1 items-start justify-center bg-canvas-soft px-4 py-16">
      <div className="w-full max-w-md space-y-6 rounded-3xl border border-line bg-canvas p-8 shadow-xl">
        <header className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">{LOGIN_TITLE}</h1>
          <p className="text-ink-soft">{SIGN_IN_TO_USE}</p>
          <p className="text-sm text-muted">
            Revisar un anuncio o preguntar a la normativa llama a modelos de IA de pago, así que las herramientas piden
            usuario y contraseña. Ver los anuncios no lo necesita.
          </p>
        </header>

        {current && !current.login_required ? (
          <p className="rounded-xl bg-canvas-sunken p-4 text-sm text-ink-soft">
            Esta instalación no pide acceso: las herramientas están abiertas.{" "}
            <Link to={returnTo} className="font-medium text-accent-strong underline-offset-2 hover:underline">
              Volver
            </Link>
          </p>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1">
              <label htmlFor={userId} className="text-xs font-medium text-muted">
                Usuario
              </label>
              <input
                id={userId}
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
                className={fieldClass}
              />
            </div>
            <div className="space-y-1">
              <label htmlFor={passwordId} className="text-xs font-medium text-muted">
                Contraseña
              </label>
              <input
                id={passwordId}
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
                className={fieldClass}
              />
            </div>
            {error && (
              <p role="alert" className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={sending}
              className="w-full rounded-lg bg-ink px-4 py-3 text-sm font-medium text-white hover:bg-ink-soft disabled:opacity-60"
            >
              {sending ? "Entrando…" : "Entrar"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
