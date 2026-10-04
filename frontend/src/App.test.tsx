import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import App from "./App";

// Mock the API client
vi.mock("./api/client", () => ({
  api: {
    getHealth: vi.fn().mockResolvedValue({ status: "ok", version: "0.9.0" }),
    getHitRate: vi.fn().mockResolvedValue({ hit_rate: 0.68, decided: 25, totals: { win: 17, loss: 8 } }),
    discoverMatches: vi.fn().mockResolvedValue({ results: {} }),
  },
}));

describe("App Smoke Test", () => {
  it("renders the main brand header", async () => {
    render(<App />);
    expect(await screen.findByText(/Colmillo/i)).toBeInTheDocument();
  });
});
