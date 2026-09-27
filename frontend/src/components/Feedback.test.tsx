import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { stubApi } from "../testing/stubApi";
import { Feedback, THANKS } from "./Feedback";

const VOTE = "POST /api/v1/feedback";

describe("feedback", () => {
  it("sends the vote with the request id and thanks once it is sent", async () => {
    const calls = stubApi({ [VOTE]: () => ({ status: 201, body: { id: 1 } }) });
    const user = userEvent.setup();
    render(<Feedback kind="regulation_answer" requestId="req-1" />);

    await user.type(screen.getByRole("textbox", { name: "Comentario" }), "  Cita un artículo que no es  ");
    await user.click(screen.getByRole("button", { name: "👎 No es correcto" }));

    expect(await screen.findByText(THANKS)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "👍 Útil" })).not.toBeInTheDocument();
    expect(calls.filter((call) => call.path === "/api/v1/feedback")).toEqual([
      {
        method: "POST",
        path: "/api/v1/feedback",
        payload: { request_id: "req-1", kind: "regulation_answer", rating: "down", comment: "Cita un artículo que no es" },
      },
    ]);
  });

  it("sends no comment when none was written", async () => {
    const calls = stubApi({ [VOTE]: () => ({ status: 201, body: { id: 1 } }) });
    const user = userEvent.setup();
    render(<Feedback kind="regulation_answer" requestId="req-1" />);

    await user.click(screen.getByRole("button", { name: "👍 Útil" }));

    await screen.findByText(THANKS);
    expect(calls.at(-1)?.payload).toMatchObject({ rating: "up", comment: null });
  });

  it("shows the error and keeps the buttons when it fails", async () => {
    stubApi({
      [VOTE]: () => ({
        status: 503,
        body: { error: { code: "feedback_unavailable", message: "No se ha podido guardar tu valoración en este momento." } },
      }),
    });
    const user = userEvent.setup();
    render(<Feedback kind="regulation_answer" requestId="req-1" />);

    await user.click(screen.getByRole("button", { name: "👍 Útil" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No se ha podido guardar tu valoración en este momento.");
    expect(screen.getByRole("button", { name: "👍 Útil" })).toBeEnabled();
  });

  it("offers no vote for a result without a request id", () => {
    render(<Feedback kind="regulation_answer" requestId={null} />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
