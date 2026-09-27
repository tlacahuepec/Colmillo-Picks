import React, { useState, useEffect } from "react";
import {
  Box,
  Grid,
  Card,
  Typography,
  Button,
  Chip,
  Select,
  Switch,
  MenuItem,
  FormControl,
  InputLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  TextField,
} from "@mui/material";
import {
  Database,
  FileSpreadsheet,
  Clock,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Archive,
} from "lucide-react";
import { api } from "../api/client";
import { CatalogCanonicalRef, CatalogEventItem, CatalogHealthSummary, CatalogSnapshotItem, CatalogSportSetting } from "../api/types";
import { isRecord, loadPageDraft, savePageDraft } from "../state/pageDrafts";

const teamName = (team?: CatalogCanonicalRef) => team?.display_name || team?.canonical_id || "";
type CatalogDraft = { sportFilter: string; newSport: string };
const defaultCatalogDraft = (): CatalogDraft => ({ sportFilter: "all", newSport: "" });
const isCatalogDraft = (value: unknown): value is CatalogDraft => isRecord(value) && typeof value.sportFilter === "string" && typeof value.newSport === "string";

export const CatalogPage: React.FC = () => {
  const [initialDraft] = useState(() => loadPageDraft("catalog", defaultCatalogDraft(), isCatalogDraft));
  const [sportFilter, setSportFilter] = useState<string>(initialDraft.sportFilter);
  const [events, setEvents] = useState<CatalogEventItem[]>([]);
  const [health, setHealth] = useState<CatalogHealthSummary | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<CatalogSnapshotItem | null>(null);
  const [snapshotModalOpen, setSnapshotModalOpen] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const [sportSettings, setSportSettings] = useState<CatalogSportSetting[]>([]);
  const [newSport, setNewSport] = useState<string>(initialDraft.newSport);
  const [savingSport, setSavingSport] = useState<string | null>(null);

  useEffect(() => {
    savePageDraft("catalog", { sportFilter, newSport });
  }, [sportFilter, newSport]);

  useEffect(() => {
    loadCatalogData();
  }, [sportFilter]);

  const loadCatalogData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, settings] = await Promise.all([
        api.listCatalogEvents({ sport: sportFilter !== "all" ? sportFilter : undefined }),
        api.listCatalogSettings(),
      ]);
      setEvents(data.items || []);
      setHealth(data.catalog || null);
      setSportSettings(settings.items || []);
    } catch (err: any) {
      setError(err.message || "Failed to load catalog events");
      setEvents([]);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSportSetting = async (sport: string, enabled: boolean) => {
    setSavingSport(sport);
    setError(null);
    try {
      await api.updateCatalogSport(sport, enabled);
      if (!enabled && sportFilter === sport) setSportFilter("all");
      await loadCatalogData();
    } catch (err: any) {
      setError(err.message || "Failed to update catalog sport");
    } finally {
      setSavingSport(null);
    }
  };

  const handleAddSport = async () => {
    const sport = newSport.trim();
    if (!sport) return;
    await handleSportSetting(sport, true);
    setNewSport("");
  };

  const handleInspectSnapshot = async (eventId: string) => {
    setSnapshotError(null);
    try {
      const snapshot = await api.getCatalogSnapshot(eventId);
      setSelectedSnapshot(snapshot);
      setSnapshotModalOpen(true);
    } catch (err: any) {
      setSnapshotError(err.message || "Failed to load event snapshot");
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshMessage("Starting Fanatics Markets refresh...");
    setError(null);
    try {
      const accepted = await api.refreshCatalog();
      let job = await api.getCatalogJob(accepted.job_id);
      while (job.state === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        job = await api.getCatalogJob(accepted.job_id);
      }
      const summary = typeof job.summary === "object" && job.summary
        ? ` Saved ${job.summary.snapshots ?? 0} snapshots and ${job.summary.market_observations ?? 0} prediction-market observations.`
        : job.summary ? ` ${job.summary}` : "";
      setRefreshMessage(`Refresh ${job.state}.${summary}`);
      await loadCatalogData();
    } catch (err: any) {
      setError(err.message || "Catalog refresh failed");
      setRefreshMessage(null);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: "-0.02em" }}>
            Daily Sports Intelligence Catalog
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            Local SQLite repository holding daily schedule preparation, canonical sports contracts, and field-level freshness.
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
          <Button variant="contained" onClick={handleRefresh} disabled={refreshing} startIcon={refreshing ? <CircularProgress size={16} color="inherit" /> : <Database size={16} />}>
            {refreshing ? "Refreshing…" : "Refresh Today's Intelligence"}
          </Button>
          <Chip
            icon={<ShieldCheck size={14} color="#10B981" />}
            label="Catalog Shadow Mode: Active"
            variant="outlined"
            sx={{ color: "success.main", borderColor: "rgba(16, 185, 129, 0.4)", fontWeight: 700 }}
          />
        </Box>
      </Box>

      {refreshMessage && <Alert severity="info" onClose={() => setRefreshMessage(null)}>{refreshMessage}</Alert>}

      {/* Error Alert */}
      {error && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={loadCatalogData}>
              Retry
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {snapshotError && (
        <Alert severity="error" onClose={() => setSnapshotError(null)}>
          {snapshotError}
        </Alert>
      )}

      <Card sx={{ p: 2.5, bgcolor: "background.paper" }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, alignItems: "center", mb: 1 }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 700 }}>Catalog Sports</Typography>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              Disabled sports stay retained locally but are hidden and skipped by future refreshes.
            </Typography>
          </Box>
          <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
            <TextField
              size="small"
              label="Add sport"
              value={newSport}
              onChange={(event) => setNewSport(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter") void handleAddSport(); }}
            />
            <Button variant="outlined" onClick={() => void handleAddSport()} disabled={!newSport.trim() || savingSport !== null}>
              Enable
            </Button>
          </Box>
        </Box>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          {sportSettings.map((setting) => (
            <Box key={setting.sport} sx={{ display: "flex", alignItems: "center", border: "1px solid", borderColor: "divider", borderRadius: 1, px: 1 }}>
              <Switch
                size="small"
                checked={setting.enabled}
                disabled={savingSport !== null}
                onChange={(_event, enabled) => void handleSportSetting(setting.sport, enabled)}
                inputProps={{ "aria-label": `Enable ${setting.sport} catalog` }}
              />
              <Typography variant="body2" sx={{ fontWeight: 700 }}>{setting.sport}</Typography>
              <Typography variant="caption" sx={{ color: "text.secondary", ml: 0.75 }}>
                {setting.retained_events} retained
              </Typography>
            </Box>
          ))}
          {sportSettings.length === 0 && <Typography variant="body2" color="text.secondary">No catalog sports discovered yet.</Typography>}
        </Box>
      </Card>

      {/* Operational Health KPIs */}
      <Grid container spacing={2}>
        {[
          { label: "Tracked Events", val: health?.events ?? 0, color: "#FFF" },
          { label: "Normalized Snapshots", val: health?.snapshots ?? 0, color: "primary.main" },
          { label: "Provider Observations", val: health?.observations ?? 0, color: "success.main" },
          { label: "Raw Archives", val: health?.raw_archives ?? 0, color: "#3B82F6" },
        ].map((kpi) => (
          <Grid item xs={12} sm={6} md={3} key={kpi.label}>
            <Card sx={{ p: 2, bgcolor: "background.paper" }}>
              <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700, textTransform: "uppercase" }}>
                {kpi.label}
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 800, color: kpi.color, fontFamily: "monospace", mt: 0.5 }}>
                {kpi.val}
              </Typography>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Filter and Events Table */}
      <Card sx={{ p: 2.5, bgcolor: "background.paper" }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>Events Catalog</Typography>
          <FormControl size="small" sx={{ width: 160 }}>
            <InputLabel>Sport</InputLabel>
            <Select value={sportFilter} label="Sport" onChange={(e) => setSportFilter(e.target.value)}>
              <MenuItem value="all">All Sports</MenuItem>
              {sportSettings.filter((setting) => setting.enabled).map((setting) => (
                <MenuItem key={setting.sport} value={setting.sport}>{setting.sport.toUpperCase()}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Canonical Event ID</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Sport / League</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Matchup</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Scheduled Kickoff</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {events.map((ev) => (
                <TableRow key={ev.event_id} hover>
                  <TableCell sx={{ fontFamily: "monospace", fontSize: "0.8rem", color: "primary.light" }}>
                    {ev.event_id}
                  </TableCell>
                  <TableCell>
                    <Chip label={ev.sport.toUpperCase()} size="small" sx={{ height: 20, fontSize: "0.68rem" }} />
                  </TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>
                    {ev.home_team && ev.away_team ? `${teamName(ev.home_team)} vs ${teamName(ev.away_team)}` : "Scheduled Match"}
                  </TableCell>
                  <TableCell sx={{ color: "text.secondary", fontSize: "0.8rem" }}>
                    {new Date(ev.start_time).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
                  </TableCell>
                  <TableCell>
                    <Chip label={ev.status} size="small" color="success" sx={{ height: 20, fontSize: "0.68rem" }} />
                  </TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      variant="outlined"
                      color="primary"
                      onClick={() => handleInspectSnapshot(ev.event_id)}
                    >
                      Inspect Snapshot
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {events.length === 0 && !loading && !error && (
                <TableRow>
                  <TableCell colSpan={6} sx={{ textAlign: "center", py: 4, color: "text.secondary" }}>
                    No events found in catalog for this filter.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Snapshot Inspector Modal */}
      <Dialog
        open={snapshotModalOpen}
        onClose={() => setSnapshotModalOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{ sx: { bgcolor: "#0D1322", p: 1 } }}
      >
        <DialogTitle sx={{ fontWeight: 800 }}>Canonical Snapshot Inspection</DialogTitle>
        <DialogContent>
          {selectedSnapshot && (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <Box sx={{ p: 1.5, bgcolor: "#070B14", borderRadius: "8px", border: "1px solid #1E293B" }}>
                <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                  Snapshot ID: {selectedSnapshot.snapshot_id} • Version: {selectedSnapshot.normalization_version}
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 700, mt: 0.5 }}>
                  Completeness: <span style={{ color: "#10B981" }}>{selectedSnapshot.completeness}</span>
                </Typography>
              </Box>

              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                <Chip label={`${selectedSnapshot.payload?.prediction_markets?.length || 0} prediction markets`} size="small" color="primary" />
                <Chip label={`${selectedSnapshot.payload?.lineups?.length || 0} lineups`} size="small" />
                <Chip label={`${selectedSnapshot.payload?.injuries?.length || 0} injuries`} size="small" />
                <Chip label={`${selectedSnapshot.payload?.missing_fields?.length || 0} missing resources`} size="small" color="warning" />
              </Box>

              {(selectedSnapshot.payload?.prediction_markets || []).length > 0 && (
                <>
                  <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Prediction Markets</Typography>
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>
                      Fanatics Markets contract data, not sportsbook odds.
                    </Typography>
                  </Box>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Market</TableCell>
                        <TableCell>Selection</TableCell>
                        <TableCell>Probability</TableCell>
                        <TableCell>Volume</TableCell>
                        <TableCell>Observed</TableCell>
                        <TableCell>Source</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {selectedSnapshot.payload.prediction_markets.map((market: any, index: number) => (
                        <TableRow key={`${market.market_id}-${market.selection}-${index}`}>
                          <TableCell>{market.market_type}</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>{market.selection}</TableCell>
                          <TableCell>{market.displayed_price || "—"}</TableCell>
                          <TableCell>{market.volume || "—"}</TableCell>
                          <TableCell>{market.observed_at ? new Date(market.observed_at).toLocaleString() : "—"}</TableCell>
                          <TableCell>
                            {market.source_url ? <a href={market.source_url} target="_blank" rel="noreferrer">View source</a> : "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </>
              )}

              {(selectedSnapshot.payload?.missing_fields || []).length > 0 && (
                <Alert severity="info">
                  This refresh does not yet include: {selectedSnapshot.payload.missing_fields.join(", ")}.
                </Alert>
              )}

              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Field-Level Freshness Evaluation
              </Typography>

              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Resource Field</TableCell>
                    <TableCell>Observed At</TableCell>
                    <TableCell>Freshness Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(selectedSnapshot.payload?.fields || []).map((f: any) => (
                    <TableRow key={f.name}>
                      <TableCell sx={{ fontFamily: "monospace", fontSize: "0.85rem" }}>{f.name}</TableCell>
                      <TableCell sx={{ color: "text.secondary" }}>{f.observed_at}</TableCell>
                      <TableCell>
                        <Chip
                          label={f.status}
                          size="small"
                          color={f.status === "FRESH" ? "success" : "warning"}
                          sx={{ height: 20, fontSize: "0.7rem", fontWeight: 700 }}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                  {(selectedSnapshot.payload?.fields || []).length === 0 && (
                    <TableRow>
                      <TableCell colSpan={3} sx={{ color: "text.secondary" }}>
                        No field-level intelligence has been collected for this snapshot yet.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSnapshotModalOpen(false)} variant="contained" color="primary">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
