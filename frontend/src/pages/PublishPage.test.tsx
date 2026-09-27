import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EXAMPLES } from "../landlord/examples";
import { myListings, recordQuickReview, saveDraft } from "../landlord/myListingsStore";
import { renderAt } from "../renderAt";
import { never, stubApi } from "../testing/stubApi";
import { AGENT_APPROVED, AGENT_CHANGES, AGENT_PAUSED } from "../testing/agentReviews";
import { APPROVED, CHANGES_REQUESTED } from "../testing/reviews";
import { AGENT_REVIEWING, CHANGED_SINCE_CHECK, DRAFT_SAVED, EMPTY_LISTING, PENDING_MODERATION, PUBLISHED } from "./PublishPage";

const REVIEW = "POST /api/v1/listings/review";
const AGENT = "POST /api/v1/listings/agent-review";
const MADRID = EXAMPLES.find((example) => example.id === "deposit-two-months")!;

const reviewPanel = () => screen.getByRole("complementary", { name: "Revisión" });

describe("publish page", () => {
  it("fills the form from an example", async () => {
    const user = userEvent.setup();
    renderAt("/publicar");

    await user.selectOptions(screen.getByRole("combobox", { name: "Rellenar con un ejemplo" }), "Dos meses de fianza (Madrid)");

    expect(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" })).toHaveValue(MADRID.input.text);
    expect(screen.getByRole("spinbutton", { name: "Precio (€/mes)" })).toHaveValue(1100);
    expect(screen.getByRole("spinbutton", { name: "Superficie útil (m²)" })).toHaveValue(68);
    expect(screen.getByRole("spinbutton", { name: "Habitaciones" })).toHaveValue(2);
    expect(screen.getByRole("textbox", { name: "Municipio" })).toHaveValue("Madrid");
    expect(screen.getByRole("combobox", { name: "Calificación energética" })).toHaveValue("D");
  });

  it("refuses an empty text without calling the API or saving anything", async () => {
    const calls = stubApi();
    const user = userEvent.setup();
    renderAt("/publicar");

    await user.click(screen.getByRole("button", { name: "Comprobar anuncio" }));

    expect(screen.getByRole("alert")).toHaveTextContent(EMPTY_LISTING);
    expect(calls.filter((call) => call.path.startsWith("/api"))).toEqual([]);
    expect(myListings()).toEqual([]);
  });

  it("sends the text and the structured fields and shows the verdict with its findings", async () => {
    const calls = stubApi({ [REVIEW]: () => ({ body: CHANGES_REQUESTED }) });
    const user = userEvent.setup();
    renderAt("/publicar");
    await user.selectOptions(screen.getByRole("combobox", { name: "Rellenar con un ejemplo" }), "Dos meses de fianza (Madrid)");

    await user.click(screen.getByRole("button", { name: "Comprobar anuncio" }));

    expect(await within(reviewPanel()).findByText("Requiere cambios")).toBeInTheDocument();
    expect(calls.filter((call) => call.path === "/api/v1/listings/review").map((call) => call.payload)).toEqual([
      MADRID.input,
    ]);
    const findings = within(reviewPanel()).getAllByRole("listitem").map((item) => item.textContent);
    // The finding that blocks publication first, whatever order the review gave them in.
    expect(findings[0]).toContain("Alta");
    expect(findings[0]).toContain("La fianza de dos mensualidades supera la legal");
    expect(findings[0]).toContain("Base legal: LAU art. 36.1");
    expect(findings[1]).toContain("Baja");
    expect(within(reviewPanel()).getByText(/Coste estimado: 0,0035 USD/)).toBeInTheDocument();
  });

  it("saves the draft to 'Mis anuncios' with the review, and keeps editing it at its own address", async () => {
    stubApi({ [REVIEW]: () => ({ body: APPROVED }) });
    const user = userEvent.setup();
    renderAt("/publicar");
    await user.type(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" }), "Piso de 2 habitaciones en Ruzafa.");

    await user.click(screen.getByRole("button", { name: "Comprobar anuncio" }));
    await within(reviewPanel()).findByText("Listo para publicar");

    const [saved] = myListings();
    expect(saved).toMatchObject({ status: "draft", input: { text: "Piso de 2 habitaciones en Ruzafa." } });
    expect(saved.quickReview).toEqual(APPROVED);
    expect(within(reviewPanel()).getByText("Respuesta cacheada · sin coste")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Mis anuncios" }));
    await user.click(screen.getByRole("link", { name: "Editar" }));
    expect(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" })).toHaveValue("Piso de 2 habitaciones en Ruzafa.");
    expect(within(reviewPanel()).getByText("Listo para publicar")).toBeInTheDocument();
  });

  it("saves a draft without checking it", async () => {
    const calls = stubApi();
    const user = userEvent.setup();
    renderAt("/publicar");
    await user.type(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" }), "Estudio en Lavapiés.");

    await user.click(screen.getByRole("button", { name: "Guardar borrador" }));

    expect(screen.getByRole("status")).toHaveTextContent(DRAFT_SAVED);
    expect(myListings()).toHaveLength(1);
    expect(calls.filter((call) => call.path.startsWith("/api"))).toEqual([]);
  });

  it("says when the listing changed after its last check", async () => {
    const { id } = saveDraft({ ...MADRID.input });
    recordQuickReview(id, CHANGES_REQUESTED);
    const user = userEvent.setup();
    renderAt(`/publicar/${id}`);
    expect(screen.queryByText(CHANGED_SINCE_CHECK)).not.toBeInTheDocument();

    await user.clear(screen.getByRole("spinbutton", { name: "Precio (€/mes)" }));
    await user.type(screen.getByRole("spinbutton", { name: "Precio (€/mes)" }), "1000");

    expect(screen.getByText(CHANGED_SINCE_CHECK)).toBeInTheDocument();
  });

  it("shows the API's error, and the draft is kept", async () => {
    stubApi({
      [REVIEW]: () => ({ status: 422, body: { error: { code: "text_too_short", message: "El texto es demasiado corto (mínimo 50 caracteres)" } } }),
    });
    const user = userEvent.setup();
    renderAt("/publicar");
    await user.type(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" }), "Piso.");

    await user.click(screen.getByRole("button", { name: "Comprobar anuncio" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("El texto es demasiado corto (mínimo 50 caracteres)");
    expect(myListings()).toHaveLength(1);
  });

  it("locks the form while it checks", async () => {
    stubApi({ [REVIEW]: never });
    const user = userEvent.setup();
    renderAt("/publicar");
    await user.type(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" }), "Piso de 2 habitaciones en Ruzafa.");

    await user.click(screen.getByRole("button", { name: "Comprobar anuncio" }));

    expect(screen.getByRole("button", { name: "Comprobando…" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" })).toBeDisabled();
  });

  it("a new listing from the header, while editing a draft, starts from an empty form", async () => {
    const { id } = saveDraft({ ...MADRID.input });
    const user = userEvent.setup();
    renderAt(`/publicar/${id}`);
    expect(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" })).toHaveValue(MADRID.input.text);

    const siteHeader = screen.getAllByRole("banner")[0];
    await user.click(within(siteHeader).getByRole("link", { name: "Publicar anuncio" }));

    expect(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" })).toHaveValue("");
    expect(within(reviewPanel()).queryByText("Requiere cambios")).not.toBeInTheDocument();
  });

  it("an approved agent review publishes the listing", async () => {
    const calls = stubApi({ [AGENT]: () => ({ body: AGENT_APPROVED }) });
    const user = userEvent.setup();
    renderAt("/publicar");
    await user.selectOptions(screen.getByRole("combobox", { name: "Rellenar con un ejemplo" }), "Dos meses de fianza (Madrid)");

    await user.click(screen.getByRole("button", { name: "Enviar a publicar" }));

    expect(await within(reviewPanel()).findByText(PUBLISHED, { exact: false })).toBeInTheDocument();
    expect(calls.filter((call) => call.path === "/api/v1/listings/agent-review").map((call) => call.payload)).toEqual([
      MADRID.input,
    ]);
    const [listing] = myListings();
    expect(listing.status).toBe("published");
    // Nothing to send again until the listing changes.
    expect(screen.getByRole("button", { name: "Enviar a publicar" })).toBeDisabled();

    await user.click(within(reviewPanel()).getByRole("link", { name: "Verlo en la búsqueda" }));
    expect(screen.getByRole("heading", { level: 1, name: "Piso exterior de 2 habitaciones en Arganzuela (Madrid), 68 m² útiles, con ascensor" })).toBeInTheDocument();
    expect(screen.getByText("Tu anuncio")).toBeInTheDocument();
  });

  it("a review that requests changes leaves it in 'Requiere cambios', with the corrected version to use", async () => {
    stubApi({ [AGENT]: () => ({ body: AGENT_CHANGES }) });
    const user = userEvent.setup();
    renderAt("/publicar");
    await user.selectOptions(screen.getByRole("combobox", { name: "Rellenar con un ejemplo" }), "Dos meses de fianza (Madrid)");

    await user.click(screen.getByRole("button", { name: "Enviar a publicar" }));

    await within(reviewPanel()).findByRole("region", { name: "Anuncio corregido" });
    expect(myListings()[0].status).toBe("changes_requested");
    expect(screen.getAllByText("Requiere cambios").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Usar esta versión" }));

    expect(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" })).toHaveValue(AGENT_CHANGES.rewrite!.text);
    expect(screen.getByText(CHANGED_SINCE_CHECK)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar a publicar" })).toBeEnabled();
  });

  it("a paused review leaves it in 'Pendiente de moderación'", async () => {
    stubApi({ [AGENT]: () => ({ status: 202, body: AGENT_PAUSED }) });
    const user = userEvent.setup();
    renderAt("/publicar");
    await user.selectOptions(screen.getByRole("combobox", { name: "Rellenar con un ejemplo" }), "Tres incumplimientos (Madrid)");

    await user.click(screen.getByRole("button", { name: "Enviar a publicar" }));

    expect(await within(reviewPanel()).findByText(PENDING_MODERATION)).toBeInTheDocument();
    expect(myListings()[0]).toMatchObject({ status: "pending_moderation", runId: "run-42" });
    expect(screen.getByRole("button", { name: "Enviar a publicar" })).toBeDisabled();
  });

  it("says the agent is reviewing while it does", async () => {
    stubApi({ [AGENT]: never });
    const user = userEvent.setup();
    renderAt("/publicar");
    await user.type(screen.getByRole("textbox", { name: "Pega o escribe tu anuncio" }), "Piso de 2 habitaciones en Ruzafa.");

    await user.click(screen.getByRole("button", { name: "Enviar a publicar" }));

    expect(within(reviewPanel()).getByText(AGENT_REVIEWING)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviando…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Comprobar anuncio" })).toBeDisabled();
  });

  it("says so when a draft does not exist", () => {
    renderAt("/publicar/no-such-draft");

    expect(screen.getByRole("heading", { level: 1, name: "Este borrador no existe." })).toBeInTheDocument();
  });
});
