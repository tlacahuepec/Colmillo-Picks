import React, { useState, useEffect } from "react";
import { AppShell } from "./components/Layout/AppShell";
import { GeneratePage } from "./pages/GeneratePage";
import { HistoryPage } from "./pages/HistoryPage";
import { BestTodayPage } from "./pages/BestTodayPage";
import { GroundingAuditPage } from "./pages/GroundingAuditPage";
import { DiagnosticsPage } from "./pages/DiagnosticsPage";
import { CatalogPage } from "./pages/CatalogPage";

const VALID_TABS = ["generate", "history", "slate", "grounding", "diagnostics", "catalog"] as const;
type TabType = (typeof VALID_TABS)[number];

function currentLocation() {
  const [tab, query = ""] = window.location.hash.replace("#", "").split("?");
  return { tab: VALID_TABS.includes(tab as TabType) ? (tab as TabType) : "generate", operationId: new URLSearchParams(query).get("operation") || undefined };
}

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabType>(() => currentLocation().tab);
  const [targetDiagnosticOpId, setTargetDiagnosticOpId] = useState<string | undefined>(() => currentLocation().operationId);

  useEffect(() => {
    const handleHashChange = () => {
      const location = currentLocation();
      setCurrentTab(location.tab);
      setTargetDiagnosticOpId(location.operationId);
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const handleTabChange = (newTab: string) => {
    if (VALID_TABS.includes(newTab as TabType)) {
      setCurrentTab(newTab as TabType);
      window.location.hash = newTab;
    }
  };

  const navigateToDiagnostics = (opId: string) => {
    setTargetDiagnosticOpId(opId);
    setCurrentTab("diagnostics");
    window.location.hash = `diagnostics?operation=${encodeURIComponent(opId)}`;
  };

  const renderPage = () => {
    switch (currentTab) {
      case "generate":
        return <GeneratePage onNavigateToDiagnostics={navigateToDiagnostics} />;
      case "history":
        return <HistoryPage onNavigateToDiagnostics={navigateToDiagnostics} />;
      case "slate":
        return <BestTodayPage onNavigateToDiagnostics={navigateToDiagnostics} />;
      case "grounding":
        return <GroundingAuditPage />;
      case "diagnostics":
        return <DiagnosticsPage initialOperationId={targetDiagnosticOpId} />;
      case "catalog":
        return <CatalogPage />;
      default:
        return <GeneratePage onNavigateToDiagnostics={navigateToDiagnostics} />;
    }
  };

  return (
    <AppShell currentTab={currentTab} onTabChange={handleTabChange}>
      {renderPage()}
    </AppShell>
  );
};

export default App;
