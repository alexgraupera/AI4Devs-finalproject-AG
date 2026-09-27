import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderAt } from "../renderAt";

describe("header", () => {
  it("on a phone keeps the links behind a menu that closes on every navigation", async () => {
    const user = userEvent.setup();
    renderAt("/");
    const menuButton = screen.getByRole("button", { name: "Menú" });
    expect(menuButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("navigation", { name: "Menú" })).not.toBeInTheDocument();

    await user.click(menuButton);
    await user.click(within(screen.getByRole("navigation", { name: "Menú" })).getByRole("link", { name: "Mis anuncios" }));

    expect(screen.getByRole("heading", { level: 1, name: "Mis anuncios" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Menú" })).not.toBeInTheDocument();
    expect(menuButton).toHaveAttribute("aria-expanded", "false");
  });
});
