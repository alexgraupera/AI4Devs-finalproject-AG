import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-24 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">Esta página no existe.</h1>
      <Link to="/" className="mt-6 inline-block rounded-lg bg-ink px-5 py-3 text-sm font-medium text-white hover:bg-ink-soft">
        Volver al inicio
      </Link>
    </div>
  );
}
