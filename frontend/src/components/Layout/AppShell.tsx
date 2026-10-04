import React, { useState, useEffect } from "react";
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Tabs,
  Tab,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Tooltip,
} from "@mui/material";
import {
  Sparkles,
  Target,
  History,
  Activity,
  Database,
  Search,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { api } from "../../api/client";
import { clearAllPageDrafts } from "../../state/pageDrafts";

interface AppShellProps {
  currentTab: string;
  onTabChange: (newTab: string) => void;
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ currentTab, onTabChange, children }) => {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiKey, setApiKey] = useState(localStorage.getItem("COLMILLO_API_KEY") || "");
  const [apiUrl, setApiUrl] = useState(localStorage.getItem("COLMILLO_API_URL") || "");
  const [healthStatus, setHealthStatus] = useState<string>("checking");
  const [hitRate, setHitRate] = useState<number | null>(null);
  const [decidedCount, setDecidedCount] = useState<number>(0);

  useEffect(() => {
    api.getHealth()
      .then(() => setHealthStatus("healthy"))
      .catch(() => setHealthStatus("offline"));

    api.getHitRate()
      .then((res) => {
        if (typeof res.hit_rate === "number") {
          setHitRate(res.hit_rate);
          setDecidedCount(res.decided || 0);
        }
      })
      .catch(() => setHitRate(null));
  }, [currentTab]);

  const handleSaveSettings = () => {
    localStorage.setItem("COLMILLO_API_KEY", apiKey);
    if (apiUrl) {
      localStorage.setItem("COLMILLO_API_URL", apiUrl);
    } else {
      localStorage.removeItem("COLMILLO_API_URL");
    }
    setSettingsOpen(false);
    window.location.reload();
  };

  const handleClearDrafts = () => {
    clearAllPageDrafts();
    window.location.reload();
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh", bgcolor: "background.default" }}>
      {/* Top Header */}
      <AppBar position="sticky" elevation={0} sx={{ bgcolor: "background.paper", borderBottom: "1px solid", borderColor: "divider" }}>
        <Toolbar sx={{ justifyContent: "space-between", px: { xs: 2, md: 3 } }}>
          {/* Brand */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Box
              sx={{
                width: 38,
                height: 38,
                borderRadius: "10px",
                background: "linear-gradient(135deg, #06B6D4, #3B82F6)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1.2rem",
                boxShadow: "0 0 15px rgba(6, 182, 212, 0.4)",
              }}
            >
              🐺
            </Box>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1.1, letterSpacing: "-0.02em" }}>
                Colmillo<span style={{ color: "#06B6D4" }}>Picks</span>
              </Typography>
              <Typography variant="caption" sx={{ color: "text.disabled", letterSpacing: "0.05em", textTransform: "uppercase", fontSize: "0.68rem" }}>
                Sports Intelligence v0.9.0
              </Typography>
            </Box>
          </Box>

          {/* Navigation Tabs (All 6 screens guaranteed) */}
          <Tabs
            value={currentTab}
            onChange={(_, val) => onTabChange(val)}
            textColor="primary"
            indicatorColor="primary"
            sx={{
              minHeight: 48,
              "& .MuiTab-root": {
                minHeight: 48,
                px: 2,
                fontSize: "0.875rem",
                fontWeight: 600,
                color: "text.secondary",
                "&.Mui-selected": { color: "primary.main" },
              },
            }}
          >
            <Tab icon={<Target size={16} />} iconPosition="start" label="Generate Pick" value="generate" />
            <Tab icon={<History size={16} />} iconPosition="start" label="Pick History & Grading" value="history" />
            <Tab icon={<Sparkles size={16} />} iconPosition="start" label="Best Today Slate" value="slate" />
            <Tab icon={<Search size={16} />} iconPosition="start" label="Grounding Audit" value="grounding" />
            <Tab icon={<Activity size={16} />} iconPosition="start" label="Diagnostics Hub" value="diagnostics" />
            <Tab icon={<Database size={16} />} iconPosition="start" label="Catalog Explorer" value="catalog" />
          </Tabs>

          {/* Quick Telemetry & Settings */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <Box sx={{ display: { xs: "none", lg: "flex" }, alignItems: "center", gap: 1.5 }}>
              <Chip
                icon={<ShieldCheck size={14} color="#10B981" />}
                label={healthStatus === "healthy" ? "API Optimal" : "API Offline"}
                size="small"
                variant="outlined"
                sx={{
                  borderColor: healthStatus === "healthy" ? "rgba(16, 185, 129, 0.4)" : "rgba(244, 63, 94, 0.4)",
                  color: healthStatus === "healthy" ? "success.main" : "error.main",
                  bgcolor: healthStatus === "healthy" ? "rgba(16, 185, 129, 0.08)" : "rgba(244, 63, 94, 0.08)",
                  fontSize: "0.75rem",
                  fontFamily: "monospace",
                }}
              />
              <Chip
                label={hitRate !== null ? `${(hitRate * 100).toFixed(1)}% Win Rate` : "No graded picks"}
                size="small"
                sx={{ bgcolor: "rgba(6, 182, 212, 0.1)", color: "primary.main", fontWeight: 700, fontFamily: "monospace" }}
              />
            </Box>
            <Tooltip title="Configure API Credentials">
              <IconButton onClick={() => setSettingsOpen(true)} sx={{ color: "text.secondary", "&:hover": { color: "text.primary" } }}>
                <Settings size={20} />
              </IconButton>
            </Tooltip>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Main Content Area */}
      <Box sx={{ flex: 1, py: 3, px: { xs: 2, md: 3 }, maxWidth: 1600, width: "100%", mx: "auto" }}>
        {children}
      </Box>

      {/* Settings Dialog */}
      <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} PaperProps={{ sx: { bgcolor: "#0D1322", p: 1, minWidth: 400 } }}>
        <DialogTitle sx={{ fontWeight: 700 }}>Connection Settings</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2, color: "text.secondary" }}>
            Configure your local Colmillo-Picks API credentials:
          </Typography>
          <TextField
            fullWidth
            label="API Base URL"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder="e.g. http://localhost:8000 (leave empty for default proxy)"
            variant="outlined"
            margin="dense"
            helperText="Direct API endpoint. Defaults to relative proxy /"
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="API Key (X-API-Key)"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="e.g. dev-key"
            variant="outlined"
            margin="dense"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClearDrafts} color="warning">Clear saved drafts</Button>
          <Button onClick={() => setSettingsOpen(false)} color="inherit">Cancel</Button>
          <Button onClick={handleSaveSettings} variant="contained" color="primary">Save & Reconnect</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
