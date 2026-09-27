import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CATALAN_OFFER_QUESTION, DEPOSIT_QUESTION } from "../regulations/questions";
import { renderAt } from "../renderAt";
import { ANSWERED, ANSWERED_FEES, NOT_COVERED } from "../testing/answers";
import { never, stubApi } from "../testing/stubApi";
import { ASSISTANT_GREETING, ASSISTANT_LAUNCHER, ASSISTANT_TITLE } from "./ListingAssistant";

const ASK = "POST /api/v1/regulations/ask";

const openAssistant = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole("button", { name: ASSISTANT_LAUNCHER }));
  return screen.getByRole("dialog", { name: ASSISTANT_TITLE });
};

const conversation = () => screen.getByRole("log", { name: "Conversación" });

describe("listing assistant", () => {
  it("is a button in the corner until it is opened, then greets with the listing's suggestions", async () => {
    const user = userEvent.setup();
    renderAt("/alquiler/palma-santa-catalina-2h");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    const assistant = await openAssistant(user);

    expect(within(assistant).getByText(ASSISTANT_GREETING)).toBeInTheDocument();
    expect(within(assistant).getByRole("button", { name: DEPOSIT_QUESTION })).toBeInTheDocument();
    expect(within(assistant).getByRole("textbox", { name: "Tu pregunta" })).toHaveFocus();
  });

  it("a suggestion asks with the listing's jurisdictions and answers in the conversation", async () => {
    const calls = stubApi({ [ASK]: () => ({ body: ANSWERED }) });
    const user = userEvent.setup();
    renderAt("/alquiler/barcelona-gracia-2h");
    await openAssistant(user);

    await user.click(screen.getByRole("button", { name: CATALAN_OFFER_QUESTION }));

    expect(await within(conversation()).findByText(ANSWERED.answer)).toBeInTheDocument();
    expect(within(conversation()).getByText(CATALAN_OFFER_QUESTION, { selector: "p" })).toBeInTheDocument();
    expect(
      within(conversation()).getByRole("link", { name: "Ley de Arrendamientos Urbanos · Artículo 36. Fianza" }),
    ).toBeInTheDocument();
    // A suggestion already asked is not offered again.
    expect(screen.queryByRole("button", { name: CATALAN_OFFER_QUESTION })).not.toBeInTheDocument();
    expect(calls.filter((call) => call.path === "/api/v1/regulations/ask").map((call) => call.payload)).toEqual([
      { question: CATALAN_OFFER_QUESTION, jurisdictions: ["state", "catalonia"] },
    ]);
  });

  it("keeps the conversation as it grows, and after closing and opening it again", async () => {
    const answers = [ANSWERED, ANSWERED_FEES];
    stubApi({ [ASK]: () => ({ body: answers.shift() }) });
    const user = userEvent.setup();
    renderAt("/alquiler/soller-centro-2h");
    await openAssistant(user);
    const field = screen.getByRole("textbox", { name: "Tu pregunta" });

    await user.type(field, "¿Cuánta fianza me pueden pedir?{Enter}");
    await within(conversation()).findByText(ANSWERED.answer);
    expect(field).toHaveValue("");
    await user.type(field, "¿Y los gastos de gestión?");
    await user.click(screen.getByRole("button", { name: "Preguntar" }));
    await within(conversation()).findByText(ANSWERED_FEES.answer);

    await user.click(screen.getByRole("button", { name: "Cerrar el asistente" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: ASSISTANT_LAUNCHER })).toHaveFocus();

    await openAssistant(user);
    expect(within(conversation()).getByText(ANSWERED.answer)).toBeInTheDocument();
    expect(within(conversation()).getByText(ANSWERED_FEES.answer)).toBeInTheDocument();
  });

  it("shows a 'no answer' without sources, and an error, in the conversation", async () => {
    const replies = [
      { body: NOT_COVERED },
      { status: 429, body: { error: { code: "rate_limited", message: "Demasiadas consultas seguidas." } } },
    ];
    stubApi({ [ASK]: () => replies.shift()! });
    const user = userEvent.setup();
    renderAt("/alquiler/bilbao-abando-3h");
    await openAssistant(user);
    const field = screen.getByRole("textbox", { name: "Tu pregunta" });

    await user.type(field, "¿Cómo declaro el alquiler en el IRPF?{Enter}");
    expect(await within(conversation()).findByRole("note")).toHaveTextContent(NOT_COVERED.answer);
    expect(within(conversation()).queryByText("Fuentes")).not.toBeInTheDocument();

    await user.type(field, "¿Cuál es la fianza?{Enter}");
    expect(await within(conversation()).findByRole("alert")).toHaveTextContent("Demasiadas consultas seguidas.");
  });

  it("says it is searching while the answer is on its way, and takes no other question meanwhile", async () => {
    stubApi({ [ASK]: never });
    const user = userEvent.setup();
    renderAt("/alquiler/palma-santa-catalina-2h");
    await openAssistant(user);

    await user.click(screen.getByRole("button", { name: DEPOSIT_QUESTION }));

    expect(within(conversation()).getByRole("status")).toHaveTextContent("Buscando en la normativa...");
    for (const suggestion of within(conversation()).getAllByRole("button")) {
      if (suggestion.textContent?.startsWith("¿")) expect(suggestion).toBeDisabled();
    }
  });

  it("sends nothing while the question is empty", async () => {
    const user = userEvent.setup();
    renderAt("/alquiler/palma-santa-catalina-2h");
    await openAssistant(user);

    expect(screen.getByRole("button", { name: "Preguntar" })).toBeDisabled();
  });

  it("closes with Escape", async () => {
    const user = userEvent.setup();
    renderAt("/alquiler/palma-santa-catalina-2h");
    await openAssistant(user);

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
