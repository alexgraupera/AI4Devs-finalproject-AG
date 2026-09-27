import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EXAMPLES } from "../landlord/examples";
import { recordQuickReview, saveDraft } from "../landlord/myListingsStore";
import { renderAt } from "../renderAt";
import { CHANGES_REQUESTED } from "../testing/reviews";
import { NO_LISTINGS } from "./MyListingsPage";

describe("my listings page", () => {
  it("lists the listings with their status and their last check", () => {
    const checked = saveDraft(EXAMPLES[1].input);
    recordQuickReview(checked.id, CHANGES_REQUESTED);
    saveDraft(EXAMPLES[0].input);
    renderAt("/mis-anuncios");

    const cards = within(screen.getByRole("list", { name: "Mis anuncios" })).getAllByRole("article");

    expect(cards).toHaveLength(2);
    const madrid = cards.find((card) => card.textContent?.includes("Arganzuela"))!;
    expect(madrid).toHaveTextContent("Borrador");
    expect(madrid).toHaveTextContent("Última comprobación: Requiere cambios");
    expect(madrid).toHaveTextContent("2 incidencias");
    expect(madrid).toHaveTextContent("Madrid · 1.100 €/mes · 68 m² · 2 hab.");
    const valencia = cards.find((card) => card.textContent?.includes("Ruzafa"))!;
    expect(valencia).toHaveTextContent("Sin comprobar todavía");
  });

  it("shows the empty state", () => {
    renderAt("/mis-anuncios");

    expect(screen.getByText(NO_LISTINGS)).toBeInTheDocument();
  });

  it("is linked from the header, and leads to writing a new listing", async () => {
    const user = userEvent.setup();
    renderAt("/");

    await user.click(screen.getByRole("link", { name: "Mis anuncios" }));
    await user.click(screen.getAllByRole("link", { name: "Publicar anuncio" }).at(-1)!);

    expect(screen.getByRole("heading", { level: 1, name: "Publica tu anuncio" })).toBeInTheDocument();
  });
});
