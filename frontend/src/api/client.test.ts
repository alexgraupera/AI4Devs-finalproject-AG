import { stubApi } from "../testing/stubApi";
import { askRegulations, SIGN_IN_REQUIRED_EVENT, type SignInRequired } from "./client";

const ASK = "POST /api/v1/regulations/ask";

function listenForSignIn() {
  const heard: string[] = [];
  const listener = (event: Event) => heard.push((event as SignInRequired).detail.returnTo);
  window.addEventListener(SIGN_IN_REQUIRED_EVENT, listener);
  return { heard, stop: () => window.removeEventListener(SIGN_IN_REQUIRED_EVENT, listener) };
}

describe("api client", () => {
  afterEach(() => window.history.pushState({}, "", "/"));

  it("a 401 sends to /acceso, keeping the page to return to", async () => {
    stubApi({ [ASK]: () => ({ status: 401, body: { error: { code: "sign_in_required", message: "Inicia sesión para usar las herramientas." } } }) });
    window.history.pushState({}, "", "/alquiler/madrid-chamberi-3h?foto=2");
    const signIn = listenForSignIn();

    await expect(askRegulations("¿Cuál es la fianza?", null)).rejects.toMatchObject({
      status: 401,
      message: "Inicia sesión para usar las herramientas.",
    });

    expect(signIn.heard).toEqual(["/alquiler/madrid-chamberi-3h?foto=2"]);
    signIn.stop();
  });

  it("the API's own 401 is a deployment fault, not a reason to sign in again", async () => {
    stubApi({ [ASK]: () => ({ status: 401, body: { error: { code: "unauthorized", message: "Clave de acceso no válida" } } }) });
    const signIn = listenForSignIn();

    await expect(askRegulations("¿Cuál es la fianza?", null)).rejects.toMatchObject({ status: 401 });

    expect(signIn.heard).toEqual([]);
    signIn.stop();
  });
});
