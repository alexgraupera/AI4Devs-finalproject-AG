import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderAt } from "../renderAt";

describe("listing page", () => {
  it("shows price, surface, rooms and energy rating", () => {
    renderAt("/alquiler/palma-santa-catalina-2h");

    expect(
      screen.getByRole("heading", { level: 1, name: "Piso luminoso de 2 habitaciones en Santa Catalina" }),
    ).toBeInTheDocument();
    const facts = screen.getAllByRole("definition").map((fact) => fact.textContent);
    expect(facts).toEqual(expect.arrayContaining(["1.350", "78", "2"]));
    const energy = screen.getByText("Certificado energético", { selector: "dt" }).parentElement!;
    expect(within(energy).getByText("E")).toBeInTheDocument();
  });

  it("says when the listing states no energy rating", () => {
    renderAt("/alquiler/girona-barri-vell-2h");

    expect(screen.getByText("Sin calificación")).toBeInTheDocument();
  });

  it("moves through the photos", async () => {
    const user = userEvent.setup();
    renderAt("/alquiler/palma-santa-catalina-2h");

    await user.click(screen.getByRole("button", { name: "Foto siguiente" }));

    expect(
      screen.getByRole("img", { name: "Piso luminoso de 2 habitaciones en Santa Catalina, foto 2 de 4" }),
    ).toBeInTheDocument();
  });

  it("shows not found for an unknown id", () => {
    renderAt("/alquiler/no-such-flat");

    expect(
      screen.getByRole("heading", { level: 1, name: "Este anuncio no existe o ya no está publicado." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver pisos en alquiler" })).toHaveAttribute("href", "/alquiler");
  });
});
