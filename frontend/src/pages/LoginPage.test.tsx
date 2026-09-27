import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderAt } from "../renderAt";
import { ANSWERED } from "../testing/answers";
import { stubApi } from "../testing/stubApi";
import { LOGIN_TITLE } from "./LoginPage";

const SESSION = "GET /bff/session";
const SIGN_IN = "POST /bff/session";
const ASK = "POST /api/v1/regulations/ask";
const SIGN_IN_REQUIRED = { error: { code: "sign_in_required", message: "Inicia sesión para usar las herramientas." } };
const LISTING = "Piso luminoso de 2 habitaciones en Santa Catalina";

const typeCredentials = async (user: ReturnType<typeof userEvent.setup>, password = "la-contraseña") => {
  await user.type(screen.getByLabelText("Usuario"), "evaluador");
  await user.type(screen.getByLabelText("Contraseña"), password);
  await user.click(screen.getByRole("button", { name: "Entrar" }));
};

describe("login page", () => {
  it("signs in and returns to the page that asked", async () => {
    let signedIn = false;
    const calls = stubApi({
      [SESSION]: () => ({ body: { login_required: true, signed_in: signedIn } }),
      [SIGN_IN]: () => {
        signedIn = true;
        return { status: 204, body: null };
      },
      [ASK]: () => (signedIn ? { body: ANSWERED } : { status: 401, body: SIGN_IN_REQUIRED }),
    });
    const user = userEvent.setup();
    renderAt("/alquiler/palma-santa-catalina-2h");

    // A tool without a session: the web server refuses it, and the app takes the person to sign in.
    await user.click(screen.getByRole("button", { name: "Pregunta tus derechos" }));
    await user.type(screen.getByRole("textbox", { name: "Tu pregunta" }), "¿Cuál es la fianza?{Enter}");
    expect(await screen.findByRole("heading", { level: 1, name: LOGIN_TITLE })).toBeInTheDocument();

    await typeCredentials(user);

    expect(await screen.findByRole("heading", { level: 1, name: LISTING })).toBeInTheDocument();
    expect(calls.filter((call) => call.path === "/bff/session" && call.method === "POST").map((call) => call.payload)).toEqual([
      { username: "evaluador", password: "la-contraseña" },
    ]);
    const header = screen.getAllByRole("banner")[0];
    expect(within(header).getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
  });

  it("shows the error on wrong credentials", async () => {
    stubApi({
      [SESSION]: () => ({ body: { login_required: true, signed_in: false } }),
      [SIGN_IN]: () => ({ status: 401, body: { error: { code: "wrong_credentials", message: "Usuario o contraseña incorrectos." } } }),
    });
    const user = userEvent.setup();
    renderAt("/acceso");

    await typeCredentials(user, "no-es");

    expect(await screen.findByRole("alert")).toHaveTextContent("Usuario o contraseña incorrectos.");
    expect(screen.getByRole("heading", { level: 1, name: LOGIN_TITLE })).toBeInTheDocument();
  });

  it("shows the lock message", async () => {
    stubApi({
      [SESSION]: () => ({ body: { login_required: true, signed_in: false } }),
      [SIGN_IN]: () => ({
        status: 429,
        body: { error: { code: "locked", message: "Demasiados intentos fallidos. Espera un minuto y vuelve a intentarlo." } },
      }),
    });
    const user = userEvent.setup();
    renderAt("/acceso");

    await typeCredentials(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("Demasiados intentos fallidos. Espera un minuto y vuelve a intentarlo.");
  });

  it("never sends anyone outside the site after signing in", async () => {
    stubApi({
      [SESSION]: () => ({ body: { login_required: true, signed_in: false } }),
      [SIGN_IN]: () => ({ status: 204, body: null }),
    });
    const user = userEvent.setup();
    renderAt(`/acceso?volver=${encodeURIComponent("//elsewhere.example/phish")}`);

    await typeCredentials(user);

    expect(await screen.findByRole("heading", { level: 1, name: /Alquila/ })).toBeInTheDocument();
  });

  it("signing out from the header asks for the login again", async () => {
    let signedIn = true;
    const calls = stubApi({
      [SESSION]: () => ({ body: { login_required: true, signed_in: signedIn } }),
      "DELETE /bff/session": () => {
        signedIn = false;
        return { status: 204, body: null };
      },
    });
    const user = userEvent.setup();
    renderAt("/");
    const header = screen.getAllByRole("banner")[0];

    await user.click(await within(header).findByRole("button", { name: "Cerrar sesión" }));

    expect(await within(header).findByRole("link", { name: "Acceder" })).toBeInTheDocument();
    expect(calls.some((call) => call.method === "DELETE" && call.path === "/bff/session")).toBe(true);
  });
});
