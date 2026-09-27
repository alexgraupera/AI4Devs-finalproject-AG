import { render, screen } from "@testing-library/react";
import { never, stubApi } from "../testing/stubApi";
import { SERVICE_DOWN, ServiceBanner, WAKING_UP } from "./ServiceBanner";

describe("service banner", () => {
  it("says the service is waking up while the API takes its time to answer", async () => {
    stubApi({ "GET /bff/service": never });

    render(<ServiceBanner noticeAfterMs={0} />);

    expect(await screen.findByRole("status")).toHaveTextContent(WAKING_UP);
  });

  it("says when the service is down", async () => {
    stubApi({ "GET /bff/service": () => ({ body: { api: "down" } }) });

    render(<ServiceBanner noticeAfterMs={0} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(SERVICE_DOWN);
  });

  it("says nothing when the API is up", async () => {
    const calls = stubApi();

    render(<ServiceBanner noticeAfterMs={10_000} />);

    await vi.waitFor(() => expect(calls).toHaveLength(1));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
