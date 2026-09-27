import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RegulationAnswer } from "../api/types";
import { renderAt } from "../renderAt";
import { never, stubApi } from "../testing/stubApi";
import { NO_MODEL_CALL, RegulationQuestion } from "./RegulationQuestion";

const ASK = "POST /api/v1/regulations/ask";

const ANSWERED: RegulationAnswer = {
  request_id: "req-1",
  answer: "La fianza es de una mensualidad de renta en el arrendamiento de vivienda.",
  citations: [
    {
      law_id: "BOE-A-1994-26003",
      law_title: "Ley de Arrendamientos Urbanos",
      article: "Artículo 36. Fianza",
      url: "https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
      chunk_id: 7,
    },
  ],
  has_answer: true,
  usage: {
    provider: "anthropic",
    model: "claude-haiku-4-5",
    input_tokens: 1200,
    output_tokens: 90,
    latency_ms: 2100,
    estimated_cost_usd: "0.0017",
    attempts: 1,
  },
  retrieved: [{ chunk_id: 7, article_title: "Artículo 36. Fianza", law_id: "BOE-A-1994-26003", score: 0.71 }],
};

const NOT_COVERED: RegulationAnswer = {
  ...ANSWERED,
  request_id: "req-2",
  answer: "No he encontrado la respuesta en la normativa indexada.",
  citations: [],
  has_answer: false,
  usage: { ...ANSWERED.usage, attempts: 0 },
  retrieved: [],
};

describe("regulation question", () => {
  it("sends the question with the listing's jurisdictions", async () => {
    const calls = stubApi({ [ASK]: () => ({ body: ANSWERED }) });
    const user = userEvent.setup();
    renderAt("/alquiler/barcelona-gracia-2h");

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
    renderAt("/alquiler/palma-santa-catalina-2h");

    await user.click(screen.getByRole("button", { name: "¿Cuánta fianza y qué garantías adicionales me pueden pedir?" }));

    await screen.findByText(ANSWERED.answer);
    expect(screen.getByRole("textbox", { name: "Tu pregunta" })).toHaveValue(
      "¿Cuánta fianza y qué garantías adicionales me pueden pedir?",
    );
    expect(calls.at(-1)?.payload).toEqual({
      question: "¿Cuánta fianza y qué garantías adicionales me pueden pedir?",
      jurisdictions: ["state"],
    });
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
