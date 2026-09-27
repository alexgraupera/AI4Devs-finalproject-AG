import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AgentReview } from "../api/types";
import { EXAMPLES } from "../landlord/examples";
import { findMyListing, recordAgentReview, saveDraft } from "../landlord/myListingsStore";
import { renderAt } from "../renderAt";
import { AGENT_PAUSED } from "../testing/agentReviews";
import { stubApi, type ApiCall } from "../testing/stubApi";
import { NO_PENDING, RUN_GONE } from "./ModerationPage";

const PENDING = "GET /api/v1/listings/agent-review/run-42";
const RESUME = "POST /api/v1/listings/agent-review/run-42/resume";
const MADRID = EXAMPLES.find((example) => example.id === "madrid-three-violations")!;

/** A listing the agent paused, as Phase 4 leaves it: waiting on run-42. */
function pausedListing() {
  const { id } = saveDraft(MADRID.input);
  recordAgentReview(id, AGENT_PAUSED);
  return id;
}

/** What the API answers once a person decided: the review finished with the findings that stand. */
const finished = (findings: AgentReview["findings"], status: AgentReview["status"] = "completed"): AgentReview => ({
  ...AGENT_PAUSED,
  status,
  run_id: null,
  pending_review: null,
  findings,
  verdict: findings.some((finding) => finding.severity === "high") ? "request_changes" : "approve",
});

const decisions = (calls: ApiCall[]) => calls.filter((call) => call.path.endsWith("/resume")).map((call) => call.payload);

describe("moderation page", () => {
  it("lists the listings waiting for a person, with the reason", async () => {
    pausedListing();
    stubApi({ [PENDING]: () => ({ body: AGENT_PAUSED }) });
    renderAt("/moderacion");

    const item = await screen.findByRole("article");
    expect(within(item).getByText(MADRID.input.text)).toBeInTheDocument();
    expect(within(item).getByText(/El revisor no ha podido respaldar todas las conclusiones/)).toBeInTheDocument();
    expect(within(item).getAllByRole("checkbox")).toHaveLength(2);
    expect(within(item).getAllByRole("checkbox").every((box) => (box as HTMLInputElement).checked)).toBe(true);
    expect(within(item).getByText(/El anuncio no dice quién paga la agencia\./)).toBeInTheDocument();
  });

  it("approving resumes with approve, and the listing follows the final review", async () => {
    const id = pausedListing();
    const calls = stubApi({
      [PENDING]: () => ({ body: AGENT_PAUSED }),
      [RESUME]: () => ({ body: finished(AGENT_PAUSED.findings) }),
    });
    const user = userEvent.setup();
    renderAt("/moderacion");

    await user.click(await screen.findByRole("button", { name: "Aprobar la revisión" }));

    expect(await screen.findByText(/Revisión aprobada: el anuncio vuelve a su anunciante con 2 incidencias\./)).toBeInTheDocument();
    expect(decisions(calls)).toEqual([{ action: "approve" }]);
    expect(findMyListing(id)).toMatchObject({ status: "changes_requested" });
    expect(screen.getByText(NO_PENDING)).toBeInTheDocument();
  });

  it("keeping only the marked findings resumes with adjust and their positions", async () => {
    const id = pausedListing();
    const calls = stubApi({
      [PENDING]: () => ({ body: AGENT_PAUSED }),
      [RESUME]: () => ({ body: finished([AGENT_PAUSED.findings[0]]) }),
    });
    const user = userEvent.setup();
    renderAt("/moderacion");
    const keepMarked = await screen.findByRole("button", { name: "Mantener solo las marcadas" });
    // With every finding marked, keeping the marked ones is approving: nothing to adjust yet.
    expect(keepMarked).toBeDisabled();

    await user.click(screen.getByRole("checkbox", { name: /Los gastos de agencia no pueden cobrarse al inquilino/ }));
    await user.click(keepMarked);

    await screen.findByText(/Revisión ajustada/);
    expect(decisions(calls)).toEqual([{ action: "adjust", keep: [0] }]);
    expect(findMyListing(id)?.agentReview?.findings).toHaveLength(1);
  });

  it("an adjustment that keeps nothing serious publishes the listing", async () => {
    const id = pausedListing();
    stubApi({
      [PENDING]: () => ({ body: AGENT_PAUSED }),
      [RESUME]: () => ({ body: finished([]) }),
    });
    const user = userEvent.setup();
    renderAt("/moderacion");

    for (const box of await screen.findAllByRole("checkbox")) await user.click(box);
    await user.click(screen.getByRole("button", { name: "Mantener solo las marcadas" }));

    expect(await screen.findByText(/sin incidencias graves, el anuncio se ha publicado\./)).toBeInTheDocument();
    expect(findMyListing(id)?.status).toBe("published");
  });

  it("discarding resumes with reject and the note, and the listing is a draft again", async () => {
    const id = pausedListing();
    const calls = stubApi({
      [PENDING]: () => ({ body: AGENT_PAUSED }),
      [RESUME]: () => ({ body: finished([], "discarded") }),
    });
    const user = userEvent.setup();
    renderAt("/moderacion");

    await user.type(await screen.findByRole("textbox", { name: "Nota para el anunciante (opcional)" }), "  Revisa la fianza.  ");
    await user.click(screen.getByRole("button", { name: "Descartar la revisión" }));

    expect(await screen.findByText(/Revisión descartada: el anuncio vuelve a borrador\./)).toBeInTheDocument();
    expect(decisions(calls)).toEqual([{ action: "reject", note: "Revisa la fianza." }]);
    expect(findMyListing(id)).toMatchObject({ status: "draft" });
    expect(findMyListing(id)?.runId).toBeUndefined();
  });

  it("a paused run that no longer exists shows the error and returns the listing to draft, so it can be sent again", async () => {
    const id = pausedListing();
    stubApi({
      [PENDING]: () => ({
        status: 404,
        body: { error: { code: "run_not_found", message: "Esta revisión ya no está disponible. Vuelve a lanzarla." } },
      }),
    });
    renderAt("/moderacion");

    expect(await screen.findByText(RUN_GONE, { exact: false })).toBeInTheDocument();
    expect(findMyListing(id)).toMatchObject({ status: "draft" });
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("shows the API's error and keeps the decision to make when resuming fails", async () => {
    pausedListing();
    stubApi({
      [PENDING]: () => ({ body: AGENT_PAUSED }),
      [RESUME]: () => ({ status: 503, body: { error: { code: "llm_unavailable", message: "El servicio de IA no está disponible en este momento" } } }),
    });
    const user = userEvent.setup();
    renderAt("/moderacion");

    await user.click(await screen.findByRole("button", { name: "Aprobar la revisión" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("El servicio de IA no está disponible en este momento");
    expect(screen.getByRole("button", { name: "Aprobar la revisión" })).toBeEnabled();
  });

  it("shows the empty state", () => {
    renderAt("/moderacion");

    expect(screen.getByText(NO_PENDING)).toBeInTheDocument();
  });

  it("is linked from the header, with how many reviews wait", async () => {
    pausedListing();
    stubApi({ [PENDING]: () => ({ body: AGENT_PAUSED }) });
    const user = userEvent.setup();
    renderAt("/");

    const link = screen.getAllByRole("link", { name: /Moderación/ })[0];
    expect(within(link).getByLabelText("1 pendientes")).toBeInTheDocument();
    await user.click(link);

    expect(screen.getByRole("heading", { level: 1, name: "Moderación" })).toBeInTheDocument();
  });
});
