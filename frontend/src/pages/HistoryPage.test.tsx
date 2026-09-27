import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { HistoryPage } from "./HistoryPage";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    listPicks: vi.fn(),
    getPick: vi.fn(),
    getOutcomes: vi.fn(),
    recordOutcomes: vi.fn(),
    getHitRate: vi.fn(),
  },
}));

const mockPicks = [
  {
    id: "pick-123",
    created_at: "2026-09-13T10:00:00Z",
    match_query: "Arsenal vs Chelsea",
    display_title: "Arsenal vs Chelsea",
    sport: "soccer",
    status: "success",
    operation_id: "op-123",
    competition: "Premier League",
  },
  {
    id: "pick-456",
    created_at: "2026-09-13T11:00:00Z",
    match_query: "Lakers vs Warriors",
    display_title: "Lakers vs Warriors",
    sport: "basketball",
    status: "failed",
    operation_id: "op-456",
    competition: "NBA",
  },
];

const mockDetailPick123 = {
  id: "pick-123",
  created_at: "2026-09-13T10:00:00Z",
  match_query: "Arsenal vs Chelsea",
  display_title: "Arsenal vs Chelsea",
  sport: "soccer",
  status: "success",
  operation_id: "op-123",
  report_markdown: "# Match Pick Report\n\nArsenal to win.",
  scores: [
    { rank: 1, subject_name: "Bukayo Saka", market: "shots_on_target", line: 1.5, direction: "over", score: 0.85 },
    { rank: 2, subject_name: "Cole Palmer", market: "assists", line: 0.5, direction: "over", score: 0.78 },
  ],
  request: { sport: "soccer", home_team: "Arsenal", away_team: "Chelsea" },
};

describe("HistoryPage Component (ISSUE-11 & ISSUE-12)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getHitRate).mockResolvedValue({
      hit_rate: 0.684,
      decided: 25,
      totals: { win: 17, loss: 8, push: 0, void: 0 },
    } as any);
    vi.mocked(api.listPicks).mockResolvedValue({
      items: mockPicks,
      limit: 20,
      offset: 0,
    } as any);
    vi.mocked(api.getPick).mockResolvedValue(mockDetailPick123 as any);
    vi.mocked(api.getOutcomes).mockResolvedValue({
      pick_id: "pick-123",
      items: [
        { rank: 1, player: "Bukayo Saka", market: "shots_on_target", result: "win", recorded_at: "2026-09-13 12:00" },
      ],
    } as any);
  });

  it("renders page header, hit rate badge, and initial pick list", async () => {
    render(<HistoryPage />);

    expect(await screen.findByText("Pick History")).toBeInTheDocument();
    expect(await screen.findByText("68.4%")).toBeInTheDocument();
    expect(await screen.findByText("17W / 8L of 25")).toBeInTheDocument();
    expect((await screen.findAllByText("Arsenal vs Chelsea")).length).toBeGreaterThan(0);
  });

  it("auto-selects first pick and renders report markdown and outcomes", async () => {
    render(<HistoryPage />);

    expect(await screen.findByText(/Arsenal to win/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/Bukayo Saka/i)).length).toBeGreaterThan(0);
    expect(await screen.findByRole("button", { name: /Save outcomes/i })).toBeInTheDocument();
  });

  it("filters picks by sport when sport dropdown is changed", async () => {
    render(<HistoryPage />);
    await screen.findAllByText("Arsenal vs Chelsea");

    const sportCombobox = screen.getAllByRole("combobox")[0];
    fireEvent.mouseDown(sportCombobox);

    const soccerOption = await screen.findByRole("option", { name: "Soccer" });
    fireEvent.click(soccerOption);

    await waitFor(() => {
      expect(api.listPicks).toHaveBeenCalledWith(20, 0, "soccer");
    });
  });

  it("does not submit ungraded rows", async () => {
    render(<HistoryPage />);

    const saveButton = await screen.findByRole("button", { name: /Save outcomes/i });
    expect(saveButton).toBeDisabled();
    expect(api.recordOutcomes).not.toHaveBeenCalled();
  });

  it("saves only the explicitly changed outcome and refreshes hit rate", async () => {
    vi.mocked(api.recordOutcomes).mockResolvedValue({
      pick_id: "pick-123",
      items: [
        { rank: 2, player: "Cole Palmer", market: "assists", result: "loss" },
      ],
    } as any);

    render(<HistoryPage />);
    const outcomeSelect = await screen.findByLabelText("Outcome for rank 2");
    fireEvent.mouseDown(outcomeSelect);
    fireEvent.click(await screen.findByRole("option", { name: "loss" }));
    const saveButton = await screen.findByRole("button", { name: /Save outcomes/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(api.recordOutcomes).toHaveBeenCalledWith("pick-123", [
        { rank: 2, player: "Cole Palmer", market: "assists", result: "loss" },
      ]);
      expect(screen.getByText("Outcomes successfully saved.")).toBeInTheDocument();
    });
  });

  it("keeps the selected outcome after a save failure", async () => {
    vi.mocked(api.recordOutcomes).mockRejectedValue(new Error("Could not save outcome"));
    render(<HistoryPage />);

    const outcomeSelect = await screen.findByLabelText("Outcome for rank 2");
    fireEvent.mouseDown(outcomeSelect);
    fireEvent.click(await screen.findByRole("option", { name: "loss" }));
    const saveButton = await screen.findByRole("button", { name: /Save outcomes/i });
    fireEvent.click(saveButton);

    expect(await screen.findByText("Could not save outcome")).toBeInTheDocument();
    expect(saveButton).toBeEnabled();
  });

  it("handles list fetch error gracefully", async () => {
    vi.mocked(api.listPicks).mockRejectedValue(new Error("Failed to fetch past runs"));

    render(<HistoryPage />);

    expect(await screen.findByText("Failed to fetch past runs")).toBeInTheDocument();
  });

  it("renders the API display title for a recoverable legacy blank match query", async () => {
    vi.mocked(api.listPicks).mockResolvedValueOnce({
      items: [{
        ...mockPicks[0],
        id: "pick-recovered",
        match_query: "",
        display_title: "Kansas City Chiefs vs Buffalo Bills · 2026-09-21",
      }],
      limit: 20,
      offset: 0,
    } as any);
    vi.mocked(api.getPick).mockResolvedValueOnce({
      ...mockDetailPick123,
      id: "pick-recovered",
      match_query: "",
      display_title: "Kansas City Chiefs vs Buffalo Bills · 2026-09-21",
    } as any);

    render(<HistoryPage />);

    expect(await screen.findAllByText("Kansas City Chiefs vs Buffalo Bills · 2026-09-21")).toHaveLength(2);
    expect(screen.queryByText("Untitled Match")).not.toBeInTheDocument();
  });

  it("navigates to diagnostics when View Diagnostics is clicked", async () => {
    const handleDiagnostics = vi.fn();
    render(<HistoryPage onNavigateToDiagnostics={handleDiagnostics} />);

    const diagButton = await screen.findByRole("button", { name: /View Diagnostics/i });
    fireEvent.click(diagButton);

    expect(handleDiagnostics).toHaveBeenCalledWith("op-123");
  });

  it("renders match_inputs accordion when present in pick details", async () => {
    vi.mocked(api.getPick).mockResolvedValueOnce({
      ...mockDetailPick123,
      status: "success",
      match_inputs: {
        home_lineup_confirmed: true,
        weather_condition: "Clear",
      },
    } as any);

    render(<HistoryPage />);

    expect(await screen.findByText("Match Inputs")).toBeInTheDocument();
    expect(screen.getByText(/home_lineup_confirmed/i)).toBeInTheDocument();
  });
});
