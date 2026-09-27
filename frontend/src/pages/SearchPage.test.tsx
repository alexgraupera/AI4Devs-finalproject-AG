import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EXAMPLES } from "../landlord/examples";
import { recordAgentReview, saveDraft } from "../landlord/myListingsStore";
import { renderAt } from "../renderAt";
import { AGENT_APPROVED } from "../testing/agentReviews";

const results = () => within(screen.getByRole("list", { name: "Resultados" })).getAllByRole("article");
const resultTitles = () => results().map((card) => within(card).getByRole("heading", { level: 2 }).textContent);

describe("search page", () => {
  it("shows the number of results for the filters in the URL", () => {
    renderAt("/alquiler?municipio=Barcelona&habitaciones=2");

    expect(screen.getByRole("heading", { level: 1, name: "2 pisos en alquiler en Barcelona" })).toBeInTheDocument();
    expect(results()).toHaveLength(2);
  });

  it("shows the municipality as the listings name it, whatever the case or accents typed", () => {
    renderAt("/alquiler?municipio=malaga");

    expect(screen.getByRole("heading", { level: 1, name: "1 piso en alquiler en Málaga" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Municipio" })).toHaveValue("Málaga");
  });

  it("narrows the results when a filter changes", async () => {
    const user = userEvent.setup();
    renderAt("/alquiler?municipio=Madrid");
    expect(results()).toHaveLength(3);

    await user.selectOptions(screen.getByRole("combobox", { name: "Precio hasta" }), "1.200 €/mes");

    expect(screen.getByRole("heading", { level: 1, name: "2 pisos en alquiler en Madrid" })).toBeInTheDocument();
    expect(results()).toHaveLength(2);
  });

  it("reorders the results when the sort changes", async () => {
    const user = userEvent.setup();
    renderAt("/alquiler?municipio=Madrid");

    await user.selectOptions(screen.getByRole("combobox", { name: "Ordenar por" }), "Precio más bajo");

    expect(resultTitles()).toEqual([
      "Estudio reformado de 1 habitación en Malasaña",
      "Piso de 2 habitaciones en Lavapiés",
      "Piso familiar de 3 habitaciones en Chamberí",
    ]);
  });

  it("shows the empty state when nothing matches, and clears the filters from it", async () => {
    const user = userEvent.setup();
    renderAt("/alquiler?municipio=Bilbao&precio_max=800");

    expect(screen.getByText("No hay pisos con estos filtros. Prueba a quitar alguno.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Resultados" })).not.toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Borrar filtros" })[0]);

    expect(screen.getByRole("heading", { level: 1, name: "16 pisos en alquiler" })).toBeInTheDocument();
  });

  it("links each result to its listing", async () => {
    const user = userEvent.setup();
    renderAt("/alquiler?municipio=Bilbao");

    await user.click(screen.getByRole("link", { name: "Piso de 3 habitaciones en Abando, junto a la Gran Vía" }));

    expect(
      screen.getByRole("heading", { level: 1, name: "Piso de 3 habitaciones en Abando, junto a la Gran Vía" }),
    ).toBeInTheDocument();
  });

  it("shows the landlord's published listing with 'Tu anuncio', and only once it is published", () => {
    const { id } = saveDraft(EXAMPLES.find((example) => example.id === "clean-valencia")!.input);
    const draftOnly = renderAt("/alquiler?municipio=Valencia");
    expect(results()).toHaveLength(2);
    draftOnly.unmount();

    recordAgentReview(id, AGENT_APPROVED);
    renderAt("/alquiler?municipio=Valencia");

    expect(results()).toHaveLength(3);
    const mine = results().find((card) => within(card).queryByText("Tu anuncio"))!;
    expect(within(mine).getByRole("heading", { level: 2 })).toHaveTextContent(
      // The first sentence of the text, cut short as a title.
      "Piso de 3 habitaciones y 2 baños en Ruzafa (Valencia), 90 m² útiles, con balcón y aire …",
    );
  });
});
