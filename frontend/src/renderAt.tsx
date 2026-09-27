import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { App } from "./App";

/** The whole app at a URL, as a person who types it in the browser gets it. For tests only. */
export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
