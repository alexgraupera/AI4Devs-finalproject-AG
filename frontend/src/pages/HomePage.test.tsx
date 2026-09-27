import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderAt } from "../renderAt";

describe("home page", () => {
  it("the search box takes you to the results for that municipality", async () => {
    const user = userEvent.setup();
    renderAt("/");

    await user.type(screen.getByRole("combobox", { name: "Municipio" }), "Madrid");
    await user.click(screen.getByRole("button", { name: "Buscar piso" }));

    expect(screen.getByRole("heading", { level: 1, name: /pisos en alquiler en Madrid$/ })).toBeInTheDocument();
  });

  it("an empty search takes you to every listing", async () => {
    const user = userEvent.setup();
    renderAt("/");

    await user.click(screen.getByRole("button", { name: "Buscar piso" }));

    expect(screen.getByRole("heading", { level: 1, name: "16 pisos en alquiler" })).toBeInTheDocument();
  });

  it("shows the demo notice", () => {
    renderAt("/");

    expect(screen.getByText(/los anuncios, las agencias y las fotos son ficticios/)).toBeInTheDocument();
  });
});
