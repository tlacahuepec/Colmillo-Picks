import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { AppShell } from "./AppShell";
import { api } from "../../api/client";

vi.mock("../../api/client", () => ({
  api: {
    getHealth: vi.fn(),
    getHitRate: vi.fn(),
  },
}));

describe("AppShell Component (ISSUE-06)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders live hit rate percentage when available", async () => {
    vi.mocked(api.getHealth).mockResolvedValue({ status: "ok" } as any);
    vi.mocked(api.getHitRate).mockResolvedValue({
      hit_rate: 0.75,
      decided: 12,
      totals: { win: 9, loss: 3, push: 0, void: 0 },
    } as any);

    render(
      <AppShell currentTab="generate" onTabChange={() => {}}>
        <div>Main Content</div>
      </AppShell>
    );

    expect(await screen.findByText("75.0% Win Rate")).toBeInTheDocument();
    expect(await screen.findByText("API Optimal")).toBeInTheDocument();
  });

  it("gracefully falls back to 'No graded picks' and 'API Offline' on error", async () => {
    vi.mocked(api.getHealth).mockRejectedValue(new Error("Connection refused"));
    vi.mocked(api.getHitRate).mockRejectedValue(new Error("API offline"));

    render(
      <AppShell currentTab="generate" onTabChange={() => {}}>
        <div>Main Content</div>
      </AppShell>
    );

    expect(await screen.findByText("No graded picks")).toBeInTheDocument();
    expect(await screen.findByText("API Offline")).toBeInTheDocument();
  });

  it("triggers onTabChange when navigation tab is clicked", async () => {
    vi.mocked(api.getHealth).mockResolvedValue({ status: "ok" } as any);
    vi.mocked(api.getHitRate).mockResolvedValue({ hit_rate: null, decided: 0 } as any);
    const handleTabChange = vi.fn();

    render(
      <AppShell currentTab="generate" onTabChange={handleTabChange}>
        <div>Main Content</div>
      </AppShell>
    );

    await screen.findByText("API Optimal");
    const slateTab = screen.getByRole("tab", { name: /Best Today Slate/i });
    fireEvent.click(slateTab);

    expect(handleTabChange).toHaveBeenCalledWith("slate");
  });
});
