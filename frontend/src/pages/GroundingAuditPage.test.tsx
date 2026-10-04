import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { GroundingAuditPage } from "./GroundingAuditPage";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    runGroundingAudit: vi.fn(),
  },
}));

const mockAuditResponse = {
  summary: {
    avg_field_fill_rate: 0.95,
    avg_source_url_presence: 0.92,
    avg_critical_null_rate: 0.01,
  },
  players: [
    {
      player: "Karl-Anthony Towns",
      fill_rate: 0.96,
      source_urls_presence: 0.94,
      critical_nulls: 0,
      confidence_score: 9.5,
      consistency_cv: 0.04,
    },
  ],
  sources: [
    { domain: "nba.com", count: 12 },
    { domain: "espn.com", count: 8 },
  ],
  bible_expected: [
    { source: "espn.com", present: true },
    { source: "statmuse.com", present: true },
  ],
};

describe("GroundingAuditPage Component (ISSUE-14)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.runGroundingAudit).mockResolvedValue(mockAuditResponse as any);
  });

  it("renders page title and configuration form", () => {
    render(<GroundingAuditPage />);

    expect(screen.getByText("Grounding Quality Audit")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run Audit/i })).toBeInTheDocument();
  });

  it("triggers audit on button click and renders results", async () => {
    render(<GroundingAuditPage />);

    const runBtn = screen.getByRole("button", { name: /Run Audit/i });
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(api.runGroundingAudit).toHaveBeenCalledWith(
        expect.objectContaining({
          num_players: 3,
          num_attempts: 2,
          use_bible_style: false,
        })
      );
    });

    expect(await screen.findByText("95.0%")).toBeInTheDocument();
    expect(await screen.findByText("Karl-Anthony Towns")).toBeInTheDocument();
    expect(await screen.findByText("nba.com")).toBeInTheDocument();
  });

  it("displays explicit error alert on API failure", async () => {
    vi.mocked(api.runGroundingAudit).mockRejectedValue(new Error("Gemini quota exceeded"));

    render(<GroundingAuditPage />);

    const runBtn = screen.getByRole("button", { name: /Run Audit/i });
    fireEvent.click(runBtn);

    expect(await screen.findByText("Gemini quota exceeded")).toBeInTheDocument();
    expect(screen.queryByText("Karl-Anthony Towns")).not.toBeInTheDocument();
  });
});
