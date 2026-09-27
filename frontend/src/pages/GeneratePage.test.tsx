import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { GeneratePage } from "./GeneratePage";
import { api } from "../api/client";
import {
  mockDiscoveryResponse,
  mockCreatePickResponse,
  mockPickDetailSuccess,
  mockPickDetailFailed,
  mockAvailabilityResponse,
} from "../mocks/fixtures/picks";

describe("GeneratePage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the page title and initial manual form", () => {
    render(<GeneratePage />);
    expect(screen.getByText("Generate Pick Report")).toBeInTheDocument();
    expect(screen.getByText("Match Suggestions")).toBeInTheDocument();
    expect(screen.getByText("Manual Pick Analysis")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Discover Today's Matches/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Generate$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Find New Suggestions/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Discard Cached Suggestions/i })).toBeInTheDocument();
  });

  it("discovers today's matches and displays fixtures grouped by sport", async () => {
    vi.spyOn(api, "discoverMatches").mockResolvedValue(mockDiscoveryResponse);

    render(<GeneratePage />);
    const discoverBtn = screen.getByRole("button", { name: /Discover Today's Matches/i });
    fireEvent.click(discoverBtn);

    expect(await screen.findByText(/Arsenal vs Liverpool/i)).toBeInTheDocument();
    expect(screen.getByText(/Boston Celtics vs LA Lakers/i)).toBeInTheDocument();
    expect(screen.getByText(/New York Yankees vs Boston Red Sox/i)).toBeInTheDocument();
    expect(screen.getByText(/Kansas City Chiefs vs Buffalo Bills/i)).toBeInTheDocument();
  });

  it("populates the manual form when 'Use Match' is clicked", async () => {
    vi.spyOn(api, "discoverMatches").mockResolvedValue(mockDiscoveryResponse);

    render(<GeneratePage />);
    fireEvent.click(screen.getByRole("button", { name: /Discover Today's Matches/i }));

    expect(await screen.findByText(/Arsenal vs Liverpool/i)).toBeInTheDocument();

    const useMatchBtns = screen.getAllByRole("button", { name: /Use Match/i });
    expect(useMatchBtns.length).toBeGreaterThan(0);
    fireEvent.click(useMatchBtns[0]); // Arsenal vs Liverpool

    const homeInput = screen.getByLabelText(/Home team/i) as HTMLInputElement;
    const awayInput = screen.getByLabelText(/Away team/i) as HTMLInputElement;
    expect(homeInput.value).toBe("Arsenal");
    expect(awayInput.value).toBe("Liverpool");
  });

  it("validates that home team and away team are required", async () => {
    render(<GeneratePage />);
    const generateBtn = screen.getByRole("button", { name: /^Generate$/i });

    // Both empty
    fireEvent.click(generateBtn);
    expect(await screen.findByText("Home team is required")).toBeInTheDocument();

    // Fill home only
    const homeInput = screen.getByLabelText(/Home team/i);
    fireEvent.change(homeInput, { target: { value: "Arsenal" } });
    fireEvent.click(generateBtn);
    expect(await screen.findByText("Away team is required")).toBeInTheDocument();
  });

  it("updates market options when switching sport to Baseball", async () => {
    render(<GeneratePage />);

    // Switch sport to Baseball via input change
    const sportInput = screen.getByTestId("manual-sport-input");
    fireEvent.change(sportInput, { target: { value: "Baseball" } });

    // MLB League and markets should now be visible
    expect(screen.getByLabelText(/League/i)).toHaveValue("MLB");
    expect(screen.getByLabelText(/Markets/i)).toBeInTheDocument();
  });

  it("executes pick creation, polls until completion, and displays markdown report", async () => {
    vi.spyOn(api, "createPick").mockResolvedValue(mockCreatePickResponse);
    vi.spyOn(api, "getPickStatus").mockResolvedValue({ id: "pick-test-123", status: "success" });
    vi.spyOn(api, "getPick").mockResolvedValue(mockPickDetailSuccess);
    vi.spyOn(api, "checkAvailability").mockResolvedValue(mockAvailabilityResponse);

    render(<GeneratePage />);

    const homeInput = screen.getByLabelText(/Home team/i);
    const awayInput = screen.getByLabelText(/Away team/i);
    fireEvent.change(homeInput, { target: { value: "Arsenal" } });
    fireEvent.change(awayInput, { target: { value: "Liverpool" } });

    const generateBtn = screen.getByRole("button", { name: /^Generate$/i });
    fireEvent.click(generateBtn);

    // Verify polling triggers and completes
    await waitFor(() => {
      expect(api.createPick).toHaveBeenCalledWith(
        expect.objectContaining({
          sport: "soccer",
          home_team: "Arsenal",
          away_team: "Liverpool",
        })
      );
    });

    // Check report markdown is displayed
    expect(await screen.findByText(/Match Pick Report: Arsenal vs Liverpool/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Bukayo Saka/i).length).toBeGreaterThan(0);

    // Check PrizePicks availability section rendered
    expect(await screen.findByText("Availability Check")).toBeInTheDocument();
    expect(screen.getAllByText(/Available on prizepicks/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Line differs: 2 vs recommended 1.5/i)).toBeInTheDocument();
    expect(screen.getByText(/Not available on prizepicks/i)).toBeInTheDocument();
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByText("Line Differs")).toBeInTheDocument();
    expect(screen.getByText("Not Available")).toBeInTheDocument();
  });

  it("handles terminal pipeline failure with error stage and message", async () => {
    vi.spyOn(api, "createPick").mockResolvedValue({
      id: "pick-test-failed",
      status: "queued",
      created_at: "2026-09-13T12:00:00Z",
    });
    vi.spyOn(api, "getPickStatus").mockResolvedValue({
      id: "pick-test-failed",
      status: "failed",
      error_stage: "feature_engineering",
      error_message: "Missing statutory player data",
    });

    render(<GeneratePage />);

    const homeInput = screen.getByLabelText(/Home team/i);
    const awayInput = screen.getByLabelText(/Away team/i);
    fireEvent.change(homeInput, { target: { value: "Arsenal" } });
    fireEvent.change(awayInput, { target: { value: "Liverpool" } });

    fireEvent.click(screen.getByRole("button", { name: /^Generate$/i }));

    expect(
      await screen.findByText(/Pipeline failed at stage feature_engineering: Missing statutory player data/i)
    ).toBeInTheDocument();
  });

  it("calls onNavigateToDiagnostics with operation_id when 'View Diagnostics' is clicked", async () => {
    vi.spyOn(api, "createPick").mockResolvedValue(mockCreatePickResponse);
    vi.spyOn(api, "getPickStatus").mockResolvedValue({ id: "pick-test-123", status: "success" });
    vi.spyOn(api, "getPick").mockResolvedValue(mockPickDetailSuccess);
    vi.spyOn(api, "checkAvailability").mockResolvedValue(mockAvailabilityResponse);

    const mockNavigate = vi.fn();
    render(<GeneratePage onNavigateToDiagnostics={mockNavigate} />);

    const homeInput = screen.getByLabelText(/Home team/i);
    const awayInput = screen.getByLabelText(/Away team/i);
    fireEvent.change(homeInput, { target: { value: "Arsenal" } });
    fireEvent.change(awayInput, { target: { value: "Liverpool" } });

    fireEvent.click(screen.getByRole("button", { name: /^Generate$/i }));

    const viewDiagBtn = await screen.findByRole("button", { name: /View Diagnostics/i });
    fireEvent.click(viewDiagBtn);

    expect(mockNavigate).toHaveBeenCalledWith("op-test-123");
  });

  it("displays persistent success alert with diagnostics link on fire-and-forget submission", async () => {
    vi.spyOn(api, "createPick").mockResolvedValue({
      id: "pick-async-999",
      status: "queued",
      created_at: "2026-09-13T12:00:00Z",
      operation_id: "op-async-999",
    });

    const mockNavigate = vi.fn();
    render(<GeneratePage onNavigateToDiagnostics={mockNavigate} />);

    fireEvent.change(screen.getByLabelText(/Home team/i), { target: { value: "Arsenal" } });
    fireEvent.change(screen.getByLabelText(/Away team/i), { target: { value: "Liverpool" } });

    // Check Fire & forget checkbox in the manual form
    const fireForgetCheckboxes = screen.getAllByRole("checkbox", { name: /Fire & forget/i });
    fireEvent.click(fireForgetCheckboxes[1]);

    fireEvent.click(screen.getByRole("button", { name: /^Generate$/i }));

    expect(
      await screen.findByText(/Pipeline is running in the background/i)
    ).toBeInTheDocument();

    const viewDiagBtn = screen.getByRole("button", { name: /View Diagnostics/i });
    fireEvent.click(viewDiagBtn);
    expect(mockNavigate).toHaveBeenCalledWith("op-async-999");
  });
});
