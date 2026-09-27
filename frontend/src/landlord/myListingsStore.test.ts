import { act, renderHook } from "@testing-library/react";
import type { ListingInput } from "../api/types";
import { AGENT_APPROVED, AGENT_CHANGES, AGENT_PAUSED } from "../testing/agentReviews";
import { APPROVED } from "../testing/reviews";
import {
  findMyListing,
  myListings,
  publishedListings,
  recordAgentReview,
  recordQuickReview,
  saveDraft,
  useMyListings,
} from "./myListingsStore";

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

  it("each outcome of the agent sets its status", () => {
    const approved = saveDraft(A_LISTING);
    const changes = saveDraft({ ...A_LISTING, text: "Otro piso. Dos meses de fianza." });
    const paused = saveDraft({ ...A_LISTING, text: "Un tercer piso. Honorarios al inquilino." });

    recordAgentReview(approved.id, AGENT_APPROVED);
    recordAgentReview(changes.id, AGENT_CHANGES);
    recordAgentReview(paused.id, AGENT_PAUSED);

    expect(findMyListing(approved.id)).toMatchObject({ status: "published", lastReview: "agent" });
    expect(findMyListing(approved.id)?.publishedAt).toBeDefined();
    expect(findMyListing(changes.id)).toMatchObject({ status: "changes_requested", agentReview: AGENT_CHANGES });
    expect(findMyListing(changes.id)?.runId).toBeUndefined();
    // The run the moderation will resume.
    expect(findMyListing(paused.id)).toMatchObject({ status: "pending_moderation", runId: "run-42" });
  });

  it("a published listing appears in the catalogue as the landlord's, with nothing made up", () => {
    const { id } = saveDraft({ ...A_LISTING, energy_rating: null, usable_surface_m2: null });
    expect(publishedListings()).toEqual([]);

    recordAgentReview(id, AGENT_APPROVED);

    const [published] = publishedListings();
    expect(published).toMatchObject({
      id,
      mine: true,
      title: "Piso de 2 habitaciones en Ruzafa",
      municipality: "Valencia",
      priceEurMonth: 1100,
      usableSurfaceM2: 0,
      rooms: 2,
      energyRating: null,
      description: A_LISTING.text,
      features: [],
    });
  });

  it("a changed text takes a published listing out of the catalogue until it is reviewed again", () => {
    const { id } = saveDraft(A_LISTING);
    recordAgentReview(id, AGENT_APPROVED);

    saveDraft({ ...A_LISTING, price_eur_month: 1300 }, id);

    expect(findMyListing(id)).toMatchObject({ status: "draft" });
    expect(findMyListing(id)?.agentReview).toBeUndefined();
    expect(publishedListings()).toEqual([]);
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
