/**
 * A fake of the web server for the tests: `fetch` answers from a table of routes and records every
 * call. `/bff/service` answers "up" unless a test says otherwise; a route nobody declared fails the
 * test loudly instead of reaching the network.
 */

type Reply = { status?: number; body: unknown };
type Handler = (payload: unknown) => Reply | Promise<Reply>;

export type ApiCall = { method: string; path: string; payload: unknown };

export function stubApi(routes: Record<string, Handler> = {}): ApiCall[] {
  const calls: ApiCall[] = [];
  const table: Record<string, Handler> = { "GET /bff/service": () => ({ body: { api: "up" } }), ...routes };

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const path = typeof input === "string" ? input : input instanceof URL ? input.pathname : input.url;
      const payload = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
      calls.push({ method, path, payload });
      const handler = table[`${method} ${path}`];
      if (!handler) throw new Error(`Unexpected call in a test: ${method} ${path}`);
      const { status = 200, body } = await handler(payload);
      return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
    }),
  );
  return calls;
}

/** A call that never answers, for what a page shows while it waits. */
export const never = (): Promise<Reply> => new Promise(() => {});
