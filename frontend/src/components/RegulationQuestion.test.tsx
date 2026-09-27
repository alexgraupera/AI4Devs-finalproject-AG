import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ANSWERED, NOT_COVERED } from "../testing/answers";
import { never, stubApi } from "../testing/stubApi";
import { NO_MODEL_CALL } from "./AnswerParts";
import { RegulationQuestion } from "./RegulationQuestion";

const ASK = "POST /api/v1/regulations/ask";

describe("regulation question", () => {
  it("sends the question with the jurisdictions it was given", async () => {
    const calls = stubApi({ [ASK]: () => ({ body: ANSWERED }) });
    const user = userEvent.setup();
    render(<RegulationQuestion jurisdictions={["state", "catalonia"]} suggestions={[]} />);

    await user.type(screen.getByRole("textbox", { name: "Tu pregunta" }), "¿Puedo tener mascotas?");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));

    await screen.findByText(ANSWERED.answer);
    expect(calls.filter((call) => call.path === "/api/v1/regulations/ask")).toEqual([
      {
        method: "POST",
        path: "/api/v1/regulations/ask",
        payload: { question: "¿Puedo tener mascotas?", jurisdictions: ["state", "catalonia"] },
      },
    ]);
  });

  it("a suggestion fills and sends the question", async () => {
    const calls = stubApi({ [ASK]: () => ({ body: ANSWERED }) });
    const user = userEvent.setup();
    render(<RegulationQuestion jurisdictions={["state"]} suggestions={["¿Cuál es la fianza legal?"]} />);

    await user.click(screen.getByRole("button", { name: "¿Cuál es la fianza legal?" }));

    await screen.findByText(ANSWERED.answer);
    expect(screen.getByRole("textbox", { name: "Tu pregunta" })).toHaveValue("¿Cuál es la fianza legal?");
    expect(calls.at(-1)?.payload).toEqual({ question: "¿Cuál es la fianza legal?", jurisdictions: ["state"] });
  });

  it("renders the answer with links to the BOE articles", async () => {
    stubApi({ [ASK]: () => ({ body: ANSWERED }) });
    const user = userEvent.setup();
    render(<RegulationQuestion jurisdictions={null} suggestions={[]} />);

    await user.type(screen.getByRole("textbox", { name: "Tu pregunta" }), "¿Cuál es la fianza?");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));

    const source = await screen.findByRole("link", { name: "Ley de Arrendamientos Urbanos · Artículo 36. Fianza" });
    expect(source).toHaveAttribute("href", "https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36");
    expect(screen.getByText(/Modelo: claude-haiku-4-5 · 1200 \+ 90 tokens · 2100 ms · Coste estimado: 0,0017 USD/)).toBeInTheDocument();
  });

  it("renders a 'no answer' as a warning without sources", async () => {
    stubApi({ [ASK]: () => ({ body: NOT_COVERED }) });
    const user = userEvent.setup();
    render(<RegulationQuestion jurisdictions={null} suggestions={[]} />);

    await user.type(screen.getByRole("textbox", { name: "Tu pregunta" }), "¿Cómo declaro el alquiler en el IRPF?");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));

    expect(await screen.findByRole("note")).toHaveTextContent(NOT_COVERED.answer);
    expect(screen.queryByText("Fuentes")).not.toBeInTheDocument();
    expect(screen.getByText(NO_MODEL_CALL)).toBeInTheDocument();
  });

  it("shows the API's error message", async () => {
    stubApi({
      [ASK]: () => ({ status: 429, body: { error: { code: "rate_limited", message: "Demasiadas consultas seguidas." } } }),
    });
    const user = userEvent.setup();
    render(<RegulationQuestion jurisdictions={null} suggestions={[]} />);

    await user.type(screen.getByRole("textbox", { name: "Tu pregunta" }), "¿Cuál es la fianza?");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Demasiadas consultas seguidas.");
  });

  it("refuses an empty question without calling the API", async () => {
    const calls = stubApi();
    const user = userEvent.setup();
    render(<RegulationQuestion jurisdictions={null} suggestions={[]} />);

    await user.click(screen.getByRole("button", { name: "Preguntar" }));

    expect(screen.getByRole("alert")).toHaveTextContent("La pregunta está vacía");
    expect(calls.filter((call) => call.path.startsWith("/api"))).toEqual([]);
  });

  it("says it is searching while the answer is on its way", async () => {
    stubApi({ [ASK]: never });
    const user = userEvent.setup();
    render(<RegulationQuestion jurisdictions={null} suggestions={[]} />);

    await user.type(screen.getByRole("textbox", { name: "Tu pregunta" }), "¿Cuál es la fianza?");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));

    expect(screen.getByRole("button", { name: "Buscando en la normativa..." })).toBeDisabled();
  });

  it("shows the fragments the answer was built from in the technical details", async () => {
    stubApi({ [ASK]: () => ({ body: ANSWERED }) });
    const user = userEvent.setup();
    render(<RegulationQuestion jurisdictions={null} suggestions={["¿Cuál es la fianza?"]} />);

    await user.click(screen.getByRole("button", { name: "¿Cuál es la fianza?" }));

    const table = await screen.findByRole("table", { name: "Fragmentos recuperados" });
    expect(within(table).getByRole("row", { name: "0.710 Artículo 36. Fianza BOE-A-1994-26003" })).toBeInTheDocument();
  });
});
