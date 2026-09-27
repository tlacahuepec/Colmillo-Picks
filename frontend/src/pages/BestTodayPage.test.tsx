import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BestTodayPage } from "./BestTodayPage";
import { api } from "../api/client";
import {
  mockCreateSlateResponse,
  mockSlateDetailSuccess,
  mockSlateDetailPartial,
  mockBatchAvailabilityResponse,
} from "../mocks/fixtures/slates";
import { SlateDetail } from "../api/types";

describe("BestTodayPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders generator form and recent slates list", async () => {
    vi.spyOn(api, "listSlates").mockResolvedValue({
      items: [mockSlateDetailSuccess],
      limit: 10,
      offset: 0,
    });
    vi.spyOn(api, "getSlate").mockResolvedValue(mockSlateDetailSuccess);

    render(<BestTodayPage />);

    expect(screen.getByText("Best Today Slate")).toBeInTheDocument();
    expect(screen.getByText("Cross-Sport Slate Generator")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Generate Best Today/i })).toBeInTheDocument();
    expect(await screen.findByText(/Recent Slates/i)).toBeInTheDocument();
  });

  it("shows a retry when the recent slate rail cannot load", async () => {
    const listSlates = vi.spyOn(api, "listSlates")
      .mockRejectedValueOnce(new Error("Temporary outage"))
      .mockResolvedValueOnce({ items: [mockSlateDetailSuccess], limit: 10, offset: 0 });
    vi.spyOn(api, "getSlate").mockResolvedValue(mockSlateDetailSuccess);

    render(<BestTodayPage />);
    expect(await screen.findByText("Temporary outage")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(listSlates).toHaveBeenCalledTimes(2));
    expect((await screen.findAllByText("slate-test-456")).length).toBeGreaterThan(0);
  });

  it("submits slate request, polls until completion, and displays ranked candidate cards", async () => {
    vi.spyOn(api, "listSlates").mockResolvedValue({ items: [], limit: 10, offset: 0 });
    vi.spyOn(api, "createSlate").mockResolvedValue(mockCreateSlateResponse);
    vi.spyOn(api, "getSlateStatus").mockResolvedValue({ id: "slate-test-456", status: "success" });
    vi.spyOn(api, "getSlate").mockResolvedValue(mockSlateDetailSuccess);

    render(<BestTodayPage />);

    const generateBtn = screen.getByRole("button", { name: /Generate Best Today/i });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(api.createSlate).toHaveBeenCalledWith(
        expect.objectContaining({
          date: expect.any(String),
          sports: ["soccer", "basketball", "baseball", "nfl"],
        })
      );
    });

    // Candidate cards displayed
    expect((await screen.findAllByText(/Bukayo Saka/i)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/LeBron James/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Aaron Judge/i).length).toBeGreaterThan(0);

    // Verification of card details (score, rank, confidence, risk flags)
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("92")).toBeInTheDocument(); // normalized_score 92.4 rounded
    expect(screen.getByText("away_fixture")).toBeInTheDocument();
    expect(screen.getByText("back_to_back")).toBeInTheDocument();
  });

  it("executes batch availability check and updates cards with platform lines and status badges", async () => {
    vi.spyOn(api, "listSlates").mockResolvedValue({ items: [mockSlateDetailSuccess], limit: 10, offset: 0 });
    vi.spyOn(api, "getSlate").mockResolvedValue(mockSlateDetailSuccess);
    vi.spyOn(api, "checkAvailabilityBatch").mockResolvedValue(mockBatchAvailabilityResponse);

    render(<BestTodayPage />);

    expect((await screen.findAllByText(/Bukayo Saka/i)).length).toBeGreaterThan(0);

    const checkAvailBtn = screen.getByRole("button", { name: /Check Availability/i });
    fireEvent.click(checkAvailBtn);

    await waitFor(() => {
      expect(api.checkAvailabilityBatch).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ player: "Bukayo Saka", market: "shots", line: 2.5 }),
          expect.objectContaining({ player: "LeBron James", market: "points", line: 25.5 }),
        ])
      );
    });

    // Verify badges and platform lines rendered
    expect(await screen.findByText("Available")).toBeInTheDocument();
    expect(screen.getByText("Line Differs")).toBeInTheDocument();
    expect(screen.getByText("Not Available")).toBeInTheDocument();
    expect(screen.getByText("Platform line: 28.5")).toBeInTheDocument();
  });

  it("handles partial pipeline statuses gracefully with partial failure summary alert", async () => {
    vi.spyOn(api, "listSlates").mockResolvedValue({ items: [mockSlateDetailPartial], limit: 10, offset: 0 });
    vi.spyOn(api, "getSlate").mockResolvedValue(mockSlateDetailPartial);

    render(<BestTodayPage />);

    expect(await screen.findByText("Partial Pipeline Results")).toBeInTheDocument();
    expect(screen.getByText(/waiting for lineup — lineup not confirmed yet/i)).toBeInTheDocument();
    expect(screen.getByText(/failed — weather delay postponed match/i)).toBeInTheDocument();
    // Candidates still render without crashing
    expect(screen.getAllByText(/Bukayo Saka/i).length).toBeGreaterThan(0);
  });

  it("loads candidate details when selecting a slate from the recent slates list", async () => {
    const pastSlate1 = { ...mockSlateDetailSuccess, id: "slate-past-1" };
    const pastSlate2 = { ...mockSlateDetailPartial, id: "slate-past-2" };

    vi.spyOn(api, "listSlates").mockResolvedValue({ items: [pastSlate1, pastSlate2], limit: 10, offset: 0 });
    vi.spyOn(api, "getSlate").mockImplementation(async (id: string) => {
      if (id === "slate-past-2") return pastSlate2;
      return pastSlate1;
    });

    render(<BestTodayPage />);

    expect((await screen.findAllByText(/slate-past-1/i)).length).toBeGreaterThan(0);

    // Click on the second slate
    const secondSlateItem = screen.getByText("slate-past-2");
    fireEvent.click(secondSlateItem);

    await waitFor(() => {
      expect(api.getSlate).toHaveBeenCalledWith("slate-past-2");
    });
    expect(await screen.findByText("Partial Pipeline Results")).toBeInTheDocument();
  });

  it("navigates to Diagnostics Hub when 'View Diagnostics' is clicked", async () => {
    vi.spyOn(api, "listSlates").mockResolvedValue({ items: [mockSlateDetailSuccess], limit: 10, offset: 0 });
    vi.spyOn(api, "getSlate").mockResolvedValue(mockSlateDetailSuccess);

    const mockNavigate = vi.fn();
    render(<BestTodayPage onNavigateToDiagnostics={mockNavigate} />);

    expect((await screen.findAllByText(/slate-test-456/i)).length).toBeGreaterThan(0);

    const viewDiagBtn = screen.getByRole("button", { name: /View Diagnostics/i });
    fireEvent.click(viewDiagBtn);

    expect(mockNavigate).toHaveBeenCalledWith("op-slate-456");
  });

  it("renders candidate source details including sportsbook link, NFL contributing factors, and score", async () => {
    const slateWithEnrichedDetails: SlateDetail = {
      ...mockSlateDetailSuccess,
      candidates: [
        {
          rank: 1,
          sport: "nfl",
          player: "Patrick Mahomes",
          subject_name: "Patrick Mahomes",
          market: "passing_touchdowns",
          line: 2.5,
          direction: "over",
          confidence: "high",
          normalized_score: 95.0,
          risk_flags: ["division_game"],
          source_match: {
            home_team: "KC Chiefs",
            away_team: "LV Raiders",
            event_date: "2026-09-13",
            kickoff_utc: "2026-09-13T20:00:00Z",
          },
          source_pick: {
            score: 0.94,
            offer: {
              sportsbook: "draftkings",
              odds_decimal: 2.1,
              observed_at: "2026-09-13T10:00:00Z",
              source_url: "https://sportsbook.draftkings.com/event/123",
            },
            explainability: {
              rationale: "Strong red-zone efficiency against bottom-ranked pass defense.",
              top_contributing_factors: [
                { factor: "Opponent Passing Defense", score: 0.92, weight: 0.4 },
                { factor: "Red Zone Pass Rate", score: 0.88, weight: 0.35 },
              ],
            },
            factors: {
              target_share: "high",
              pressure_rate: "low",
            },
            llm_rationale: "Mahomes has 3+ TDs in 4 of last 5 division matchups.",
          },
        },
      ],
    };

    vi.spyOn(api, "listSlates").mockResolvedValue({ items: [slateWithEnrichedDetails], limit: 10, offset: 0 });
    vi.spyOn(api, "getSlate").mockResolvedValue(slateWithEnrichedDetails);

    render(<BestTodayPage />);

    const card = await screen.findByTestId("candidate-card-1");
    expect(card).toBeInTheDocument();
    expect(card.textContent).toContain("Patrick Mahomes");

    const detailsSummary = screen.getByText(/Details: Patrick Mahomes — passing_touchdowns/i);
    fireEvent.click(detailsSummary);

    const sourceLink = screen.getByRole("link", { name: /Sportsbook source/i });
    expect(sourceLink).toHaveAttribute("href", "https://sportsbook.draftkings.com/event/123");

    expect(screen.getByText("0.94")).toBeInTheDocument();
    expect(screen.getByText(/Opponent Passing Defense: 0.92 \(weight 0.40\)/i)).toBeInTheDocument();
    expect(screen.getByText(/target_share: high, pressure_rate: low/i)).toBeInTheDocument();
  });
});
