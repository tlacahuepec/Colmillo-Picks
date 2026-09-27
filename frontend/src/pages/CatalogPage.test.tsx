import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { CatalogPage } from "./CatalogPage";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    listCatalogEvents: vi.fn(),
    getCatalogSnapshot: vi.fn(),
    refreshCatalog: vi.fn(),
    getCatalogJob: vi.fn(),
    listCatalogSettings: vi.fn(),
    updateCatalogSport: vi.fn(),
  },
}));

const mockEvents = [
  {
    event_id: "soccer:event:real-001",
    sport: "soccer",
    league: "premier_league",
    start_time: "2026-09-13T15:00:00Z",
    status: "scheduled",
    home_team: { entity_type: "team", canonical_id: "soccer:team:arsenal", display_name: "Arsenal" },
    away_team: { entity_type: "team", canonical_id: "soccer:team:chelsea", display_name: "Chelsea" },
  },
  {
    event_id: "basketball:event:real-002",
    sport: "basketball",
    league: "nba",
    start_time: "2026-09-13T19:30:00Z",
    status: "scheduled",
    home_team: { entity_type: "team", canonical_id: "basketball:team:lakers", display_name: "Lakers" },
    away_team: { entity_type: "team", canonical_id: "basketball:team:warriors", display_name: "Warriors" },
  },
];

const mockHealth = {
  available: true,
  operational: true,
  path: "data/catalog.db",
  events: 2,
  snapshots: 2,
  observations: 10,
  raw_archives: 4,
  jobs_by_state: { success: 2 },
};

const mockSnapshot = {
  snapshot_id: "snap-soccer-001",
  event_id: "soccer:event:real-001",
  created_at: "2026-09-13T14:30:00Z",
  as_of: "2026-09-13T14:30:00Z",
  completeness: "COMPLETE",
  normalization_version: "v1.0",
  payload: {
    event: { id: "soccer:event:real-001" },
    fields: [
      { name: "markets.prizepicks", observed_at: "5 min ago", status: "FRESH" },
      { name: "lineups.confirmed", observed_at: "10 min ago", status: "FRESH" },
    ],
    prediction_markets: [
      {
        market_id: "market-1", market_type: "moneyline", selection: "Arsenal",
        displayed_price: "52%", volume: "1234", observed_at: "2026-09-13T14:30:00Z",
        source_url: "https://fanaticsmarkets.com/",
      },
    ],
    lineups: [],
    injuries: [],
    missing_fields: ["official_odds", "weather"],
  },
};

describe("CatalogPage Component (ISSUE-14)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listCatalogEvents).mockResolvedValue({
      items: mockEvents,
      limit: 100,
      offset: 0,
      catalog: mockHealth as any,
    } as any);
    vi.mocked(api.getCatalogSnapshot).mockResolvedValue(mockSnapshot as any);
    vi.mocked(api.listCatalogSettings).mockResolvedValue({ items: [
      { sport: "baseball", enabled: true, retained_events: 0, discovered_at: "2026-09-19T00:00:00Z", updated_at: "2026-09-19T00:00:00Z" },
      { sport: "tennis", enabled: false, retained_events: 65, discovered_at: "2026-09-19T00:00:00Z", updated_at: "2026-09-19T00:00:00Z" },
    ] });
    vi.mocked(api.updateCatalogSport).mockResolvedValue({ sport: "tennis", enabled: true });
    vi.mocked(api.refreshCatalog).mockResolvedValue({ job_id: "job-1", status: "queued", run_date: "2026-09-15" });
    vi.mocked(api.getCatalogJob).mockResolvedValue({ job_id: "job-1", run_date: "2026-09-15", state: "success", summary: { snapshots: 1, market_observations: 2 } });
  });

  it("renders live catalog events and health counters", async () => {
    render(<CatalogPage />);

    expect(await screen.findByText("Daily Sports Intelligence Catalog")).toBeInTheDocument();
    expect(await screen.findByText("Arsenal vs Chelsea")).toBeInTheDocument();
    expect(await screen.findByText("Lakers vs Warriors")).toBeInTheDocument();
  });

  it("opens snapshot inspection modal on click", async () => {
    render(<CatalogPage />);
    await screen.findByText("Arsenal vs Chelsea");

    const inspectBtns = screen.getAllByRole("button", { name: /Inspect Snapshot/i });
    fireEvent.click(inspectBtns[0]);

    await waitFor(() => {
      expect(api.getCatalogSnapshot).toHaveBeenCalledWith("soccer:event:real-001");
      expect(screen.getByText(/Canonical Snapshot Inspection/i)).toBeInTheDocument();
      expect(screen.getByText(/snap-soccer-001/i)).toBeInTheDocument();
      expect(screen.getByText("markets.prizepicks")).toBeInTheDocument();
      expect(screen.getByText("Fanatics Markets contract data, not sportsbook odds.")).toBeInTheDocument();
      expect(screen.getByText("Arsenal")).toBeInTheDocument();
      expect(screen.getByText("52%")).toBeInTheDocument();
      expect(screen.getByText(/official_odds, weather/i)).toBeInTheDocument();
    });
  });

  it("displays explicit error alert on failure without loading mock events", async () => {
    vi.mocked(api.listCatalogEvents).mockRejectedValue(new Error("Catalog database locked"));

    render(<CatalogPage />);

    expect(await screen.findByText("Catalog database locked")).toBeInTheDocument();
    // Ensure mock data is NOT rendered
    expect(screen.queryByText("nba:event:20260913-001")).not.toBeInTheDocument();
    expect(screen.queryByText("Boston Celtics")).not.toBeInTheDocument();
  });

  it("runs the manual intelligence refresh and reloads catalog data", async () => {
    render(<CatalogPage />);
    await screen.findByText("Arsenal vs Chelsea");

    fireEvent.click(screen.getByRole("button", { name: /Refresh Today's Intelligence/i }));

    await waitFor(() => {
      expect(api.refreshCatalog).toHaveBeenCalled();
      expect(api.getCatalogJob).toHaveBeenCalledWith("job-1");
      expect(screen.getByText(/Refresh success.*Saved 1 snapshots/i)).toBeInTheDocument();
    });
  });

  it("shows persistent catalog sport controls and enables a disabled sport", async () => {
    render(<CatalogPage />);

    const tennis = await screen.findByRole("checkbox", { name: "Enable tennis catalog" });
    expect(screen.getByText("65 retained")).toBeInTheDocument();
    fireEvent.click(tennis);

    await waitFor(() => {
      expect(api.updateCatalogSport).toHaveBeenCalledWith("tennis", true);
    });
  });
});
