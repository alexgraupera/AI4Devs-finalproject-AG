import { act, renderHook } from "@testing-library/react";
import type { ListingInput } from "../api/types";
import { APPROVED } from "../testing/reviews";
import { findMyListing, myListings, recordQuickReview, saveDraft, useMyListings } from "./myListingsStore";

const KEY = "umbral-my-listings";

const A_LISTING: ListingInput = {
  text: "Piso de 2 habitaciones en Ruzafa. 1.100 € al mes. Fianza de una mensualidad.",
  price_eur_month: 1100,
  usable_surface_m2: 80,
  rooms: 2,
  municipality: "Valencia",
  energy_rating: "D",
};

describe("my listings store", () => {
  it("saves a draft and reads it back after a reload", () => {
    const saved = saveDraft(A_LISTING);

    // A reload starts from what the browser kept, not from anything in memory.
    const kept = localStorage.getItem(KEY);
    localStorage.clear();
    localStorage.setItem(KEY, kept!);

    expect(myListings()).toEqual([saved]);
    expect(saved).toMatchObject({ input: A_LISTING, status: "draft" });
  });

  it("records the quick review on the draft", () => {
    const { id } = saveDraft(A_LISTING);

    recordQuickReview(id, APPROVED);

    expect(findMyListing(id)?.quickReview).toEqual(APPROVED);
    // A check is advice while writing: it does not move the listing towards publication.
    expect(findMyListing(id)?.status).toBe("draft");
  });

  it("updates an existing draft instead of duplicating it", () => {
    const { id } = saveDraft(A_LISTING);

    saveDraft({ ...A_LISTING, price_eur_month: 1000 }, id);

    expect(myListings()).toHaveLength(1);
    expect(findMyListing(id)?.input.price_eur_month).toBe(1000);
  });

  it("drops the quick review when the text it was of changes, and keeps it when nothing did", () => {
    const { id } = saveDraft(A_LISTING);
    recordQuickReview(id, APPROVED);

    saveDraft(A_LISTING, id);
    expect(findMyListing(id)?.quickReview).toEqual(APPROVED);

    saveDraft({ ...A_LISTING, text: `${A_LISTING.text} Dos meses de fianza.` }, id);
    expect(findMyListing(id)?.quickReview).toBeUndefined();
  });

  it("starts empty when the stored value is unreadable or storage throws", () => {
    localStorage.setItem(KEY, "{not json");
    expect(myListings()).toEqual([]);

    localStorage.setItem(KEY, JSON.stringify([{ id: 1 }, "nonsense"]));
    expect(myListings()).toEqual([]);

    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    expect(myListings()).toEqual([]);
    getItem.mockRestore();
  });

  it("tells the pages when a listing is saved", () => {
    const { result } = renderHook(() => useMyListings());
    expect(result.current).toEqual([]);

    act(() => {
      saveDraft(A_LISTING);
    });

    expect(result.current).toHaveLength(1);
  });
});
