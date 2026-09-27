import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { DiagnosticsPage } from "./DiagnosticsPage";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    listDiagnostics: vi.fn(),
    getDiagnosticDetail: vi.fn(),
    exportDiagnostic: vi.fn(),
    getDiagnosticHealth: vi.fn(),
  },
}));

const mockOperations = [
  {
    operation_id: "op-test-101",
    service: "api",
    sport: "nba",
    home_team: "NY Knicks",
    away_team: "SA Spurs",
    outcome: "success",
    duration_ms: 24,
    started_at: "2026-09-13T12:00:00Z",
    updated_at: "2026-09-13T12:00:01Z",
    summary: "Generated basketball props successfully.",
    events: [
      { event: "discover", stage: "discovery", level: "INFO", duration_ms: 6, timestamp: "2026-09-13T12:00:00.100Z", outcome: "success" },
      { event: "score", stage: "scoring", level: "INFO", duration_ms: 18, timestamp: "2026-09-13T12:00:00.200Z", outcome: "success" },
    ],
  },
  {
    operation_id: "op-test-102",
    service: "worker",
    sport: "soccer",
    outcome: "failed",
    duration_ms: 110,
    started_at: "2026-09-13T12:05:00Z",
    summary: "Roster discovery timed out.",
    events: [
      { event: "discover", stage: "discovery", level: "ERROR", duration_ms: 110, timestamp: "2026-09-13T12:05:01.000Z", outcome: "failed" },
    ],
  },
];

describe("DiagnosticsPage Component (ISSUE-13)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getDiagnosticHealth).mockResolvedValue({
      healthy: true,
      status: "ok",
      counters: { active_operations: 2 },
      queue_depth: 0,
    } as any);
    vi.mocked(api.listDiagnostics).mockResolvedValue({
      items: mockOperations,
      limit: 20,
      offset: 0,
    } as any);
    vi.mocked(api.getDiagnosticDetail).mockResolvedValue({
      operation: mockOperations[0],
      events: mockOperations[0].events,
      completeness: { status: "complete" },
    } as any);
  });

  it("renders live operations and health metrics from backend", async () => {
    render(<DiagnosticsPage />);

    expect(await screen.findByText("Diagnostics Hub")).toBeInTheDocument();
    expect(await screen.findByText("Healthy")).toBeInTheDocument();
    expect(await screen.findByText("2 Runs")).toBeInTheDocument();
    expect((await screen.findAllByText(/op-test-101/i)).length).toBeGreaterThan(0);
    expect(await screen.findByText(/op-test-102/i)).toBeInTheDocument();
    expect((await screen.findAllByText("NY Knicks vs SA Spurs")).length).toBeGreaterThan(0);
    expect(await screen.findByText("SOCCER run · op-test-")).toBeInTheDocument();
  });

  it("displays pipeline stages when operation is selected", async () => {
    render(<DiagnosticsPage />);

    expect(await screen.findByText("Pipeline Stage Progression")).toBeInTheDocument();
    expect(await screen.findByText("discovery")).toBeInTheDocument();
    expect(await screen.findByText("scoring")).toBeInTheDocument();
  });

  it("displays explicit error alert on API failure without loading mock data", async () => {
    vi.mocked(api.listDiagnostics).mockRejectedValue(new Error("Telemetry service unavailable"));

    render(<DiagnosticsPage />);

    expect(await screen.findByText("Telemetry service unavailable")).toBeInTheDocument();
    // Ensure mock data is NOT present
    expect(screen.queryByText(/op-slate-20260912-001/i)).not.toBeInTheDocument();
  });

  it("triggers sanitized diagnostic ZIP download", async () => {
    const fakeBlob = new Blob(["PK fake zip"], { type: "application/zip" });
    vi.mocked(api.exportDiagnostic).mockResolvedValue(fakeBlob as any);

    render(<DiagnosticsPage />);
    await screen.findAllByText(/op-test-101/i);

    const exportBtn = screen.getByRole("button", { name: /Sanitized Report/i });
    fireEvent.click(exportBtn);

    await waitFor(() => {
      expect(api.exportDiagnostic).toHaveBeenCalledWith("op-test-101");
    });
  });

  it("renders what to do next guidance and completeness text for selected operation", async () => {
    render(<DiagnosticsPage />);

    expect(await screen.findByText(/What to do next:/i)).toBeInTheDocument();
    expect(screen.getByText(/No action is needed\. You can download a report to keep a record\./i)).toBeInTheDocument();
    expect(screen.getByText(/Completeness:/i)).toBeInTheDocument();
  });

  it("renders event recorded cause and excluded inputs metadata", async () => {
    const opWithMetadata = {
      ...mockOperations[1],
      events: [
        {
          event: "enrich",
          stage: "enrichment",
          level: "WARNING",
          duration_ms: 45,
          timestamp: "2026-09-13T12:05:01.000Z",
          outcome: "partial",
          metadata: {
            error_code: "rate_limited",
            reason_counts: { missing_odds: 4, injury_doubt: 2 },
          },
        },
      ],
    };

    vi.mocked(api.getDiagnosticDetail).mockResolvedValue({
      operation: opWithMetadata,
      events: opWithMetadata.events,
      completeness: { status: "possibly_incomplete" },
    } as any);

    render(<DiagnosticsPage />);

    expect(await screen.findByText(/Recorded cause: rate limited/i)).toBeInTheDocument();
    expect(screen.getByText(/Excluded inputs: missing odds: 4, injury doubt: 2/i)).toBeInTheDocument();
    expect(screen.getByText(/Some diagnostic events may be missing/i)).toBeInTheDocument();
  });

  it("automatically queries and selects operation when initialOperationId is provided", async () => {
    render(<DiagnosticsPage initialOperationId="op-test-102" />);

    await waitFor(() => {
      expect(api.listDiagnostics).toHaveBeenCalledWith(
        expect.objectContaining({ operation_id: "op-test-102" })
      );
    });
  });
});
