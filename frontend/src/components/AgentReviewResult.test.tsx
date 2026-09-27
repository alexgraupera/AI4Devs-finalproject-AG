import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AGENT_APPROVED, AGENT_CHANGES, AGENT_PAUSED } from "../testing/agentReviews";
import { AgentReviewResult, NEW_FIGURES_WARNING, PLACEHOLDERS_WARNING, USE_REWRITE } from "./AgentReviewResult";

describe("agent review result", () => {
  it("shows the cited findings with links to the BOE", () => {
    render(<AgentReviewResult review={AGENT_CHANGES} />);

    expect(screen.getByText("Requiere cambios")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ley 29/1994, de 24 de noviembre, de Arrendamientos Urbanos · Artículo 36. Fianza" })).toHaveAttribute(
      "href",
      "https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
    );
    expect(screen.getByText("Base legal: LAU art. 20.1")).toBeInTheDocument();
    expect(
      screen.getByText("Se han descartado 1 incidencias que el anuncio o la normativa consultada no respaldaban."),
    ).toBeInTheDocument();
  });

  it("lists the findings the critic doubts, with its reason", () => {
    render(<AgentReviewResult review={AGENT_PAUSED} />);

    expect(screen.getByText("Pendiente de moderación")).toBeInTheDocument();
    expect(screen.getByText("El revisor pone en duda 1 de estas incidencias")).toBeInTheDocument();
    const fees = screen.getByText("Los gastos de agencia no pueden cobrarse al inquilino").closest("li")!;
    expect(within(fees).getByText(/El anuncio no dice quién paga la agencia\./)).toBeInTheDocument();
    const deposit = screen.getByText("La fianza de dos mensualidades supera la legal").closest("li")!;
    expect(within(deposit).queryByText(/El revisor la pone en duda/)).not.toBeInTheDocument();
  });

  it("'Usar esta versión' hands the corrected text over", async () => {
    const onUse = vi.fn();
    const user = userEvent.setup();
    render(<AgentReviewResult review={AGENT_CHANGES} onUseRewrite={onUse} />);

    await user.click(screen.getByRole("button", { name: USE_REWRITE }));

    expect(onUse).toHaveBeenCalledWith(AGENT_CHANGES.rewrite!.text);
  });

  it("warns about the gaps to fill and the new figures", () => {
    render(<AgentReviewResult review={AGENT_CHANGES} />);

    const rewrite = screen.getByRole("region", { name: "Anuncio corregido" });
    expect(within(rewrite).getByText(`${PLACEHOLDERS_WARNING}calificación energética`)).toBeInTheDocument();
    expect(within(rewrite).getByText(`${NEW_FIGURES_WARNING}1.000 €`)).toBeInTheDocument();
    // Without a way to edit the listing (a published one being read), there is nothing to use it in.
    expect(within(rewrite).queryByRole("button", { name: USE_REWRITE })).not.toBeInTheDocument();
  });

  it("shows the agent's steps and the cost per step", () => {
    render(<AgentReviewResult review={AGENT_CHANGES} />);

    expect(screen.getByText("Pasos del agente (3)")).toBeInTheDocument();
    expect(screen.getByText("1. ✅ Comprobar los datos del anuncio")).toBeInTheDocument();
    expect(screen.getByText("2. ✅ Consultar la normativa")).toBeInTheDocument();
    expect(screen.getByText("Compruebo el límite de la fianza.")).toBeInTheDocument();
    expect(screen.getByText("El revisor no respalda alguna incidencia; el motivo está en la revisión.")).toBeInTheDocument();
    const costs = screen.getByRole("table", { name: "Coste por paso" });
    expect(within(costs).getByRole("row", { name: /Razonamiento del agente 3 19\.100 9\.0 s 0,0215 USD/ })).toBeInTheDocument();
    expect(within(costs).getByRole("row", { name: /Revisor 1 3\.300 2\.1 s 0,0036 USD/ })).toBeInTheDocument();
  });

  it("says when nothing was found", () => {
    render(<AgentReviewResult review={AGENT_APPROVED} />);

    expect(screen.getByText("Listo para publicar")).toBeInTheDocument();
    expect(screen.getByText("No se han detectado incidencias.")).toBeInTheDocument();
  });
});
