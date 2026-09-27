import "@testing-library/jest-dom/vitest";
import { forgetSession } from "./api/sessionStore";
import { stubApi } from "./testing/stubApi";

// jsdom has no layout: scrolling is a no-op there, and its default implementation logs an error.
window.scrollTo = vi.fn();
Element.prototype.scrollIntoView = vi.fn();

// No test reaches the network: every page starts with a web server that only says the API is up.
beforeEach(() => {
  stubApi();
});

afterEach(() => {
  vi.unstubAllGlobals();
  forgetSession();
  localStorage.clear();
});
