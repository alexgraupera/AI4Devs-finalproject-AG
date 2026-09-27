import type { RentalListing } from "../catalogue/catalogue";
import { findListing } from "../catalogue/catalogue";
import {
  CATALAN_OFFER_QUESTION,
  DEPOSIT_QUESTION,
  ENERGY_QUESTION,
  FEES_QUESTION,
  jurisdictionsOf,
  MINIMUM_INFORMATION_QUESTION,
  suggestedQuestions,
} from "./questions";

const listing = (id: string): RentalListing => {
  const found = findListing(id);
  if (!found) throw new Error(`no listing ${id}`);
  return found;
};

const withDescription = (description: string, overrides: Partial<RentalListing> = {}): RentalListing => ({
  ...listing("bilbao-abando-3h"),
  description,
  ...overrides,
});

describe("suggested questions", () => {
  it("suggests the deposit question when the listing mentions a deposit", () => {
    expect(suggestedQuestions(listing("palma-santa-catalina-2h"))).toContain(DEPOSIT_QUESTION);
    expect(suggestedQuestions(withDescription("Piso con aval bancario de seis meses."))).toContain(DEPOSIT_QUESTION);
  });

  it("suggests the fees question when the listing charges agency fees", () => {
    expect(suggestedQuestions(listing("soller-centro-2h"))).toContain(FEES_QUESTION);
    expect(suggestedQuestions(withDescription("Gastos de gestión: 300 €."))).toContain(FEES_QUESTION);
    expect(suggestedQuestions(withDescription("Piso exterior y luminoso."))).not.toContain(FEES_QUESTION);
  });

  it("suggests the energy rating question when the listing does not state one", () => {
    expect(suggestedQuestions(listing("girona-barri-vell-2h"))).toContain(ENERGY_QUESTION);
    expect(suggestedQuestions(listing("soller-centro-2h"))).toContain(ENERGY_QUESTION);
    expect(suggestedQuestions(listing("bilbao-abando-3h"))).not.toContain(ENERGY_QUESTION);
  });

  it("always suggests the minimum information question", () => {
    expect(suggestedQuestions(withDescription("Piso exterior y luminoso."))).toEqual([MINIMUM_INFORMATION_QUESTION]);
  });

  it("asks about the Catalan offer only for a listing in Catalonia", () => {
    expect(suggestedQuestions(listing("barcelona-gracia-2h"))).toContain(CATALAN_OFFER_QUESTION);
    expect(suggestedQuestions(listing("madrid-chamberi-3h"))).not.toContain(CATALAN_OFFER_QUESTION);
  });
});

describe("jurisdictions of a listing", () => {
  it("searches state and Catalan law for a listing in Catalonia, state law elsewhere", () => {
    expect(jurisdictionsOf(listing("girona-barri-vell-2h"))).toEqual(["state", "catalonia"]);
    expect(jurisdictionsOf(listing("valencia-ruzafa-2h"))).toEqual(["state"]);
  });
});
