import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderAt } from "../renderAt";
import { stubApi } from "../testing/stubApi";

const ANSWER = {
  request_id: "req-1",
  answer: "Una mensualidad.",
  citations: [],
  has_answer: true,
  usage: {
    provider: "anthropic",
    model: "claude-haiku-4-5",
    input_tokens: 1,
    output_tokens: 1,
    latency_ms: 1,
    estimated_cost_usd: null,
    attempts: 1,
  },
  retrieved: [],
};

describe("regulations page", () => {
  it("is linked from the header", async () => {
    const user = userEvent.setup();
    renderAt("/");

    await user.click(screen.getByRole("link", { name: "Normativa" }));

    expect(screen.getByRole("heading", { level: 1, name: "Pregunta a la normativa" })).toBeInTheDocument();
  });

  it("searches the whole corpus by default, and only the scope chosen otherwise", async () => {
    const calls = stubApi({ "POST /api/v1/regulations/ask": () => ({ body: ANSWER }) });
    const user = userEvent.setup();
    renderAt("/normativa");
    const question = screen.getByRole("textbox", { name: "Tu pregunta" });

    await user.type(question, "¿Cuál es la fianza?");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));
    await screen.findByText("Una mensualidad.");
    await user.selectOptions(screen.getByRole("combobox", { name: "Ámbito" }), "Cataluña");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));

    await vi.waitFor(() => expect(calls.filter((call) => call.path === "/api/v1/regulations/ask")).toHaveLength(2));
    const asked = calls.filter((call) => call.path === "/api/v1/regulations/ask").map((call) => call.payload);
    expect(asked).toEqual([
      { question: "¿Cuál es la fianza?", jurisdictions: null },
      { question: "¿Cuál es la fianza?", jurisdictions: ["catalonia"] },
    ]);
  });
});
