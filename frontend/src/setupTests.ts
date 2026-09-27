import "@testing-library/jest-dom/vitest";

// jsdom has no layout: scrolling is a no-op there, and its default implementation logs an error.
window.scrollTo = vi.fn();
Element.prototype.scrollIntoView = vi.fn();

afterEach(() => {
  localStorage.clear();
});
