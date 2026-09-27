import React, { useState, useEffect, useRef } from "react";
import {
  Box,
  Grid,
  Card,
  Typography,
  Button,
  Chip,
  TextField,
  Select,
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
  LinearProgress,
  Alert,
} from "@mui/material";
import {
  Activity,
  Download,
  Key,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  ShieldAlert,
} from "lucide-react";
import { api } from "../api/client";
import { DiagnosticCompleteness, DiagnosticOperation } from "../api/types";
import { isRecord, loadPageDraft, savePageDraft } from "../state/pageDrafts";

export function getNextAction(operation: DiagnosticOperation): string {
  const code = (operation.metadata || {}).error_code;
  const actions: Record<string, string> = {
    timeout: "Try again later. If it repeats, download the report so the provider timing can be checked.",
    rate_limited: "Wait before trying again; the provider is limiting requests.",
    configuration_error: "Ask the app administrator to check the provider configuration and include this report.",
    invalid_output: "Try once more. If validation keeps failing, download the report for investigation.",
    missing_citations: "Verified sources were unavailable. Try again when more matchup information is published.",
    fixture_not_found: "Check the teams and match date, then try again.",
    storage_error: "Check History before submitting again, and share this report with the administrator.",
  };
  if (code && actions[code]) {
    return actions[code];
  }
  const outcomeActions: Record<string, string> = {
    running: "Refresh to check progress. Avoid submitting the same query again while it is running.",
    queued: "The operation is waiting for a worker. Refresh to check progress.",
    success: "No action is needed. You can download a report to keep a record.",
    no_picks: "No verified picks qualified. Check the match date or try later when more data is available.",
    partial: "Review the available results and failed stages before deciding whether to retry.",
  };
  return outcomeActions[operation.outcome] || "Download the diagnostic ZIP and include it when reporting this problem.";
}

export function getCompletenessText(value: any): string {
  if (typeof value === "boolean") {
    return value ? "Complete" : "Partial — some diagnostic records are missing.";
  }
  if (value && typeof value === "object") {
    if (value.truncated || value.has_more) {
      return "Partial — more events exist than this view includes. Download the report for a larger snapshot.";
    }
    const status = value.status;
    const explanations: Record<string, string> = {
      possibly_incomplete: "Some diagnostic events may be missing because collection dropped events.",
      interrupted: "The recording process stopped; the job's final outcome is unconfirmed.",
      expired: "Detailed events expired; the retained summary may still be available.",
      pruned: "Some events were removed to stay within the storage budget.",
      truncated: "This operation reached the event limit; some details were omitted.",
      legacy_summary_only: "Only the saved result is available; detailed diagnostics were not recorded.",
    };
    if (status && explanations[status]) return explanations[status];
    if (typeof value.complete === "boolean") return getCompletenessText(value.complete);
    if (value.retention_may_apply) return "Snapshot of retained events; older records may be unavailable.";
    return value.status || "Completeness details are available in the report.";
  }
  return "Completeness was not reported.";
}

export function operationTitle(operation: DiagnosticOperation): string {
  const home = operation.home_team?.trim();
  const away = operation.away_team?.trim();
  if (home && away) return `${home} vs ${away}`;
  const sport = operation.sport?.toUpperCase() || "Operation";
  return `${sport} run · ${operation.operation_id.slice(0, 8)}`;
}

interface DiagnosticsPageProps {
  initialOperationId?: string;
}

type DiagnosticsDraft = { operationQuery: string; sportFilter: string; outcomeFilter: string; serviceFilter: string; selectedOperationId: string | null };
const defaultDiagnosticsDraft = (): DiagnosticsDraft => ({ operationQuery: "", sportFilter: "all", outcomeFilter: "", serviceFilter: "", selectedOperationId: null });
const isDiagnosticsDraft = (value: unknown): value is DiagnosticsDraft => isRecord(value) && typeof value.operationQuery === "string" && typeof value.sportFilter === "string" && typeof value.outcomeFilter === "string" && typeof value.serviceFilter === "string" && (typeof value.selectedOperationId === "string" || value.selectedOperationId === null);

export const DiagnosticsPage: React.FC<DiagnosticsPageProps> = ({ initialOperationId }) => {
  const [initialDraft] = useState(() => loadPageDraft("diagnostics", defaultDiagnosticsDraft(), isDiagnosticsDraft));
  const [operationQuery, setOperationQuery] = useState<string>(initialOperationId || initialDraft.operationQuery);
  const [sportFilter, setSportFilter] = useState<string>(initialDraft.sportFilter);
  const [outcomeFilter, setOutcomeFilter] = useState<string>(initialDraft.outcomeFilter);
  const [serviceFilter, setServiceFilter] = useState<string>(initialDraft.serviceFilter);
  const [operations, setOperations] = useState<DiagnosticOperation[]>([]);
  const [selectedOp, setSelectedOp] = useState<DiagnosticOperation | null>(null);
  const [selectedOperationId, setSelectedOperationId] = useState<string | null>(initialOperationId || initialDraft.selectedOperationId);
  const [selectedCompleteness, setSelectedCompleteness] = useState<DiagnosticCompleteness | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [diagHealth, setDiagHealth] = useState<any>(null);
  const [adminOpen, setAdminOpen] = useState<boolean>(false);
  const [adminKey, setAdminKey] = useState<string>("");
  const [isAdminUnlocked, setIsAdminUnlocked] = useState<boolean>(false);
  const detailRequestRef = useRef(0);

  useEffect(() => {
    savePageDraft("diagnostics", { operationQuery, sportFilter, outcomeFilter, serviceFilter, selectedOperationId });
  }, [operationQuery, sportFilter, outcomeFilter, serviceFilter, selectedOperationId]);

  useEffect(() => {
    if (initialOperationId) {
      setOperationQuery(initialOperationId);
      loadDiagnostics(initialOperationId);
    }
  }, [initialOperationId]);

  useEffect(() => {
    loadDiagnostics();
  }, [sportFilter, outcomeFilter, serviceFilter]);

  useEffect(() => {
    api.getDiagnosticHealth()
      .then((h) => setDiagHealth(h))
      .catch(() => setDiagHealth(null));
  }, []);

  const handleSelectOp = async (op: DiagnosticOperation) => {
    const requestId = detailRequestRef.current + 1;
    detailRequestRef.current = requestId;
    setSelectedOp(op);
    setSelectedOperationId(op.operation_id);
    try {
      const detail = await api.getDiagnosticDetail(op.operation_id);
      if (detailRequestRef.current !== requestId) return;
      if (detail) {
        if (detail.completeness) {
          setSelectedCompleteness(detail.completeness);
        }
        if (detail.operation) {
          setSelectedOp({
            ...detail.operation,
            events: detail.events || detail.operation.events || [],
          });
        }
      }
    } catch {
      // Keep existing op on error
    }
  };

  const loadDiagnostics = async (overrideQuery?: string) => {
    setLoading(true);
    setError(null);
    const queryToUse = overrideQuery !== undefined ? overrideQuery : operationQuery;
    try {
      const res = await api.listDiagnostics({
        sport: sportFilter !== "all" ? sportFilter : undefined,
        outcome: outcomeFilter || undefined,
        service: serviceFilter || undefined,
        operation_id: queryToUse || undefined,
        limit: 20,
      });
      const items = res.items || [];
      setOperations(items);
      if (items.length > 0) {
        handleSelectOp(items.find((item) => item.operation_id === selectedOperationId) || items[0]);
      } else {
        setSelectedOp(null);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load diagnostic telemetry");
      setOperations([]);
      setSelectedOp(null);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadReport = async () => {
    if (selectedOp?.operation_id) {
      try {
        const zipBlob = await api.exportDiagnostic(selectedOp.operation_id);
        const url = URL.createObjectURL(zipBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `diagnostic-${selectedOp.operation_id}.zip`;
        a.click();
        return;
      } catch {
        // Fall back to JSON report if export failed
      }
    }
    const json = JSON.stringify(selectedOp || operations, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sanitized-diagnostic-report-${selectedOp?.operation_id || "full"}.json`;
    a.click();
  };

  const avgLatency = operations.length > 0
    ? Math.round(operations.reduce((acc, o) => acc + (o.duration_ms || 0), 0) / operations.length)
    : null;

  const healthStatusLabel = diagHealth?.status === "ok" || diagHealth?.available || diagHealth?.healthy
    ? "Healthy"
    : diagHealth
    ? "Degraded"
    : "—";

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Header */}
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: "-0.02em" }}>
          Diagnostics Hub
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          Live observability and telemetry across pipeline runs, catalog leases, and worker executions.
        </Typography>
      </Box>

      {/* Top Controls Bar */}
      <Card sx={{ p: 2.5, bgcolor: "background.paper" }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              size="small"
              fullWidth
              placeholder="Search by Operation ID / Pick ID / Slate ID..."
              value={operationQuery}
              onChange={(e) => setOperationQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadDiagnostics()}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Sport</InputLabel>
              <Select value={sportFilter} label="Sport" onChange={(e) => setSportFilter(e.target.value)}>
                <MenuItem value="all">All Sports</MenuItem>
                <MenuItem value="nba">NBA</MenuItem>
                <MenuItem value="nfl">NFL</MenuItem>
                <MenuItem value="mlb">MLB</MenuItem>
                <MenuItem value="soccer">Soccer</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Outcome</InputLabel>
              <Select value={outcomeFilter} label="Outcome" onChange={(e) => setOutcomeFilter(e.target.value)}>
                <MenuItem value="">All Outcomes</MenuItem>
                <MenuItem value="success">Success</MenuItem>
                <MenuItem value="failed">Failed</MenuItem>
                <MenuItem value="running">Running</MenuItem>
                <MenuItem value="no_picks">No Picks</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box sx={{ display: "flex", gap: 1.5, justifyContent: { xs: "flex-start", md: "flex-end" } }}>
              <Button variant="contained" color="primary" onClick={() => loadDiagnostics()} startIcon={<RotateCcw size={16} />}>
                Filter
              </Button>
              <Button
                variant="outlined"
                color="secondary"
                onClick={() => setAdminOpen(true)}
                startIcon={<Key size={16} />}
              >
                {isAdminUnlocked ? "Admin Active" : "Admin Unlock"}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => loadDiagnostics()}>
              Retry
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {/* KPI Overview Tiles (Real live metrics) */}
      <Grid container spacing={2}>
        {[
          { label: "System Health", val: healthStatusLabel, color: healthStatusLabel === "Healthy" ? "success.main" : "warning.main" },
          { label: "Operations Recorded", val: `${operations.length} Runs`, color: "primary.main" },
          { label: "Queue Depth", val: `${diagHealth?.queue_depth ?? 0}`, color: "#3B82F6" },
          { label: "Avg Execution Latency", val: avgLatency !== null ? `${avgLatency} ms` : "—", color: "#FFF" },
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

      {diagHealth?.counters && (
        <Box sx={{ px: 0.5, mt: -1.5, color: "text.secondary" }}>
          <Typography variant="caption" sx={{ fontFamily: "monospace" }}>
            Events waiting to save: <strong>{diagHealth.queue_depth ?? 0}</strong> · Dropped events: <strong>{diagHealth.counters.dropped_events ?? 0}</strong> · Storage failures: <strong>{diagHealth.counters.write_failures ?? 0}</strong>
          </Typography>
        </Box>
      )}

      {/* Main Two-Column View: Operations Table (Left) + Detail & Stage Pipeline (Right) */}
      <Grid container spacing={3}>
        {/* Left: Operations Grid */}
        <Grid item xs={12} md={6}>
          <Card sx={{ bgcolor: "background.paper", overflow: "hidden" }}>
            <TableContainer sx={{ maxHeight: 600 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ bgcolor: "#0D1322", fontWeight: 700 }}>Match</TableCell>
                    <TableCell sx={{ bgcolor: "#0D1322", fontWeight: 700 }}>Operation ID</TableCell>
                    <TableCell sx={{ bgcolor: "#0D1322", fontWeight: 700 }}>Sport</TableCell>
                    <TableCell sx={{ bgcolor: "#0D1322", fontWeight: 700 }}>Duration</TableCell>
                    <TableCell sx={{ bgcolor: "#0D1322", fontWeight: 700 }}>Outcome</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {operations.map((op) => (
                    <TableRow
                      key={op.operation_id}
                      hover
                      onClick={() => handleSelectOp(op)}
                      selected={selectedOp?.operation_id === op.operation_id}
                      sx={{ cursor: "pointer" }}
                    >
                      <TableCell sx={{ fontSize: "0.8rem", fontWeight: 700 }}>
                        {operationTitle(op)}
                      </TableCell>
                      <TableCell sx={{ fontFamily: "monospace", fontSize: "0.8rem", color: selectedOp?.operation_id === op.operation_id ? "primary.light" : "text.primary" }}>
                        {op.operation_id.length > 20 ? `${op.operation_id.substring(0, 20)}...` : op.operation_id}
                      </TableCell>
                      <TableCell>
                        <Chip label={(op.sport || "ALL").toUpperCase()} size="small" sx={{ height: 20, fontSize: "0.68rem" }} />
                      </TableCell>
                      <TableCell sx={{ fontFamily: "monospace", fontSize: "0.78rem" }}>
                        {op.duration_ms ? `${op.duration_ms} ms` : "—"}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={op.outcome}
                          size="small"
                          color={op.outcome === "success" ? "success" : op.outcome === "failed" ? "error" : "default"}
                          sx={{ height: 20, fontSize: "0.68rem" }}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                  {operations.length === 0 && !loading && !error && (
                    <TableRow>
                      <TableCell colSpan={5} sx={{ textAlign: "center", py: 3, color: "text.secondary" }}>
                        No operations recorded yet.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Card>
        </Grid>

        {/* Right: Selected Operation Detail & Visual Stage Timeline */}
        <Grid item xs={12} md={6}>
          {selectedOp ? (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
              {/* Operation Summary Card */}
              <Card sx={{ p: 2.5, bgcolor: "background.paper" }}>
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1.5 }}>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 800 }}>Operation Summary</Typography>
                    <Typography variant="caption" sx={{ fontFamily: "monospace", color: "text.secondary" }}>
                      {selectedOp.operation_id}
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 700, mt: 0.5 }}>
                      {operationTitle(selectedOp)}
                    </Typography>
                  </Box>
                  <Button
                    variant="outlined"
                    size="small"
                    color="primary"
                    onClick={handleDownloadReport}
                    startIcon={<Download size={14} />}
                  >
                    Sanitized Report
                  </Button>
                </Box>

                <Box sx={{ p: 1.5, bgcolor: "rgba(0,0,0,0.25)", borderRadius: "8px", mb: 2 }}>
                  <Typography variant="body2" sx={{ color: "text.primary", lineHeight: 1.6 }}>
                    {selectedOp.summary || "The operation completed successfully."}
                  </Typography>
                </Box>

                <Box sx={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 1, fontSize: "0.85rem", mb: 2 }}>
                  <div><span style={{ color: "#94A3B8" }}>Service:</span> <strong>{selectedOp.service}</strong></div>
                  <div><span style={{ color: "#94A3B8" }}>Sport:</span> <strong>{(selectedOp.sport || "unknown").toUpperCase()}</strong></div>
                  <div><span style={{ color: "#94A3B8" }}>Duration:</span> <strong>{selectedOp.duration_ms} ms</strong></div>
                  <div><span style={{ color: "#94A3B8" }}>Started:</span> {new Date(selectedOp.started_at).toLocaleTimeString()}</div>
                  <div><span style={{ color: "#94A3B8" }}>Outcome:</span> <strong style={{ color: selectedOp.outcome === "success" ? "#10B981" : "#F43F5E" }}>{selectedOp.outcome}</strong></div>
                </Box>

                {/* Completeness Status */}
                <Box sx={{ p: 1.2, bgcolor: "rgba(255,255,255,0.03)", borderRadius: "6px", mb: 1.5 }}>
                  <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                    <strong>Completeness:</strong> {getCompletenessText(selectedCompleteness || (selectedOp as any).completeness)}
                  </Typography>
                </Box>

                {/* What To Do Next Guidance Callout */}
                <Box sx={{ p: 1.5, bgcolor: "rgba(6, 182, 212, 0.08)", border: "1px solid rgba(6, 182, 212, 0.2)", borderRadius: "6px" }}>
                  <Typography variant="body2" sx={{ fontSize: "0.82rem", color: "#E2E8F0" }}>
                    <strong style={{ color: "#06B6D4" }}>What to do next:</strong> {getNextAction(selectedOp)}
                  </Typography>
                </Box>
              </Card>

              {/* Visual Pipeline Stage Timeline */}
              <Card sx={{ p: 2.5, bgcolor: "background.paper" }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>
                  Pipeline Stage Progression
                </Typography>
                <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                  {(selectedOp.events || []).map((ev, idx) => (
                    <Box key={idx} sx={{ p: 1.5, bgcolor: "#070B14", borderRadius: "8px", border: "1px solid #1E293B" }}>
                      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 0.5 }}>
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                          <CheckCircle2 size={16} color={ev.outcome === "failed" ? "#F43F5E" : "#10B981"} />
                          <Typography variant="body2" sx={{ fontWeight: 700 }}>
                            {ev.stage || ev.event}
                          </Typography>
                        </Box>
                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.8 }}>
                          {ev.outcome && (
                            <Chip
                              label={ev.outcome}
                              size="small"
                              color={ev.outcome === "success" ? "success" : ev.outcome === "failed" ? "error" : "default"}
                              sx={{ height: 20, fontSize: "0.65rem" }}
                            />
                          )}
                          <Chip label={`${ev.duration_ms || 3} ms`} size="small" sx={{ height: 20, fontSize: "0.7rem", fontFamily: "monospace" }} />
                        </Box>
                      </Box>
                      <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                        Event: {ev.event} • Level: {ev.level} • {new Date(ev.timestamp).toLocaleTimeString()}
                      </Typography>
                      {ev.metadata?.error_code && (
                        <Typography variant="caption" sx={{ color: "error.light", display: "block", mt: 0.3 }}>
                          Recorded cause: {String(ev.metadata.error_code).replace(/_/g, " ")}
                        </Typography>
                      )}
                      {ev.metadata?.reason_counts && Object.keys(ev.metadata.reason_counts).length > 0 && (
                        <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 0.3 }}>
                          Excluded inputs: {Object.entries(ev.metadata.reason_counts).map(([r, c]) => `${r.replace(/_/g, " ")}: ${c}`).slice(0, 10).join(", ")}
                        </Typography>
                      )}
                    </Box>
                  ))}
                  {(!selectedOp.events || selectedOp.events.length === 0) && (
                    <Typography variant="body2" sx={{ color: "text.secondary", py: 2, textAlign: "center" }}>
                      No discrete events recorded for this operation.
                    </Typography>
                  )}
                </Box>
              </Card>

              {/* Admin Unlocked Technical Stack Trace (If unlocked) */}
              {isAdminUnlocked && (
                <Card sx={{ p: 2.5, bgcolor: "#0D1322", border: "1px solid #F43F5E" }}>
                  <Typography variant="subtitle2" sx={{ color: "error.light", fontWeight: 700, mb: 1 }}>
                    Admin Unredacted Technical Telemetry
                  </Typography>
                  <Box sx={{ p: 1.5, bgcolor: "#070B14", borderRadius: "6px", fontFamily: "monospace", fontSize: "0.75rem", overflowX: "auto" }}>
                    <pre style={{ margin: 0 }}>
                      {JSON.stringify(selectedOp, null, 2)}
                    </pre>
                  </Box>
                </Card>
              )}
            </Box>
          ) : (
            <Card sx={{ p: 6, textAlign: "center", bgcolor: "background.paper", borderStyle: "dashed" }}>
              <Activity size={40} color="#64748B" style={{ marginBottom: 12 }} />
              <Typography variant="h6" sx={{ color: "text.secondary" }}>
                Select an operation from the left table to inspect telemetry and execution stages
              </Typography>
            </Card>
          )}
        </Grid>
      </Grid>

      {/* Admin Unlock Dialog */}
      <Dialog open={adminOpen} onClose={() => setAdminOpen(false)}>
        <DialogTitle>Unlock Admin Telemetry</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
            Provide the system admin key (<code>COLMILLO_ADMIN_API_KEY</code>) to view unredacted exceptions, stack traces, and internal worker IDs.
          </Typography>
          <TextField
            autoFocus
            fullWidth
            type="password"
            label="Admin API Key"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAdminOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={() => {
              if (adminKey) {
                setIsAdminUnlocked(true);
                setAdminOpen(false);
              }
            }}
          >
            Unlock
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
