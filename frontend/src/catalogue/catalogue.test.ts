import { findListing, municipalities, searchListings } from "./catalogue";
import { CATALOGUE } from "./listings";

describe("catalogue", () => {
  it("filters by municipality", () => {
    const results = searchListings({ municipality: "Barcelona" });

    expect(results.length).toBeGreaterThan(0);
    expect(results.every((listing) => listing.municipality === "Barcelona")).toBe(true);
  });

  it("filters by municipality without caring about accents or case", () => {
    expect(searchListings({ municipality: "malaga" }).map((listing) => listing.municipality)).toEqual(["Málaga"]);
  });

  it("filters by maximum price", () => {
    const results = searchListings({ maxPrice: 1000 });

    expect(results.length).toBeGreaterThan(0);
    expect(results.every((listing) => listing.priceEurMonth <= 1000)).toBe(true);
    expect(results).toHaveLength(CATALOGUE.filter((listing) => listing.priceEurMonth <= 1000).length);
  });

  it("filters by minimum rooms", () => {
    const results = searchListings({ minRooms: 3 });

    expect(results.length).toBeGreaterThan(0);
    expect(results.every((listing) => listing.rooms >= 3)).toBe(true);
  });

  it("filters by minimum surface", () => {
    const results = searchListings({ minSurface: 90 });

    expect(results.length).toBeGreaterThan(0);
    expect(results.every((listing) => listing.usableSurfaceM2 >= 90)).toBe(true);
  });

  it("combines the filters", () => {
    const results = searchListings({ municipality: "Madrid", maxPrice: 1200, minRooms: 2 });

    expect(results.map((listing) => listing.id)).toEqual(["madrid-lavapies-2h"]);
  });

  it("sorts newest first by default", () => {
    const dates = searchListings({}).map((listing) => listing.publishedAt);

    expect(dates).toEqual([...dates].sort().reverse());
    expect(dates).toHaveLength(CATALOGUE.length);
  });

  it("sorts by price, ascending and descending", () => {
    const ascending = searchListings({}, "price_asc").map((listing) => listing.priceEurMonth);
    const descending = searchListings({}, "price_desc").map((listing) => listing.priceEurMonth);

    expect(ascending).toEqual([...ascending].sort((a, b) => a - b));
    expect(descending).toEqual([...ascending].reverse());
  });

  it("sorts by surface", () => {
    const surfaces = searchListings({}, "surface_desc").map((listing) => listing.usableSurfaceM2);

    expect(surfaces).toEqual([...surfaces].sort((a, b) => b - a));
  });

  it("never reorders the catalogue itself", () => {
    const before = CATALOGUE.map((listing) => listing.id);

    searchListings({}, "price_asc");

    expect(CATALOGUE.map((listing) => listing.id)).toEqual(before);
  });

  it("finds a listing by id", () => {
    expect(findListing("bilbao-abando-3h")?.municipality).toBe("Bilbao");
  });

  it("returns undefined for an unknown id", () => {
    expect(findListing("no-such-flat")).toBeUndefined();
  });

  it("lists every municipality once, alphabetically", () => {
    const names = municipalities();

    expect(names).toEqual([...new Set(names)]);
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, "es")));
    expect(names).toContain("Palma");
  });
});
