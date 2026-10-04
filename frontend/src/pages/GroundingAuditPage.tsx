import React, { useEffect, useState } from "react";
import {
  Box,
  Grid,
  Card,
  Typography,
  Button,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  FormControlLabel,
  Checkbox,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Alert,
} from "@mui/material";
import {
  Search,
  CheckCircle2,
  XCircle,
  Play,
  FileCheck,
  Globe,
  BookOpen,
} from "lucide-react";
import { api } from "../api/client";
import { isRecord, loadPageDraft, savePageDraft } from "../state/pageDrafts";

type GroundingDraft = { numPlayers: number; numAttempts: number; useBibleStyle: boolean };
const defaultGroundingDraft = (): GroundingDraft => ({ numPlayers: 3, numAttempts: 2, useBibleStyle: false });
const isGroundingDraft = (value: unknown): value is GroundingDraft => isRecord(value) && typeof value.numPlayers === "number" && typeof value.numAttempts === "number" && typeof value.useBibleStyle === "boolean";

export const GroundingAuditPage: React.FC = () => {
  const [initialDraft] = useState(() => loadPageDraft("grounding", defaultGroundingDraft(), isGroundingDraft));
  const [numPlayers, setNumPlayers] = useState<number>(initialDraft.numPlayers);
  const [numAttempts, setNumAttempts] = useState<number>(initialDraft.numAttempts);
  const [useBibleStyle, setUseBibleStyle] = useState<boolean>(initialDraft.useBibleStyle);
  const [running, setRunning] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const [progressText, setProgressText] = useState<string>("");
  const [auditData, setAuditData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    savePageDraft("grounding", { numPlayers, numAttempts, useBibleStyle });
  }, [numPlayers, numAttempts, useBibleStyle]);

  const handleRunAudit = async () => {
    setRunning(true);
    setError(null);
    setProgress(10);
    setProgressText("Initializing Gemini search-grounding client...");

    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) {
          clearInterval(timer);
          return 90;
        }
        return prev + 25;
      });
    }, 600);

    try {
      const res = await api.runGroundingAudit({
        num_players: numPlayers,
        num_attempts: numAttempts,
        use_bible_style: useBibleStyle,
      });
      clearInterval(timer);
      setProgress(100);
      setAuditData(res);
    } catch (err: any) {
      clearInterval(timer);
      setProgress(100);
      setError(err.message || "Failed to execute grounding quality audit");
      setAuditData(null);
    } finally {
      setRunning(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Header & Description */}
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: "-0.02em" }}>
          Grounding Quality Audit
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          Evaluates Gemini search grounding quality: field-fill rate, source-URL presence, critical null rate, and cross-attempt consistency.
        </Typography>
      </Box>

      {/* Audit Configuration Card */}
      <Card sx={{ p: 3, bgcolor: "background.paper" }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Players to Test</InputLabel>
              <Select value={numPlayers} label="Players to Test" onChange={(e: any) => setNumPlayers(e.target.value)}>
                <MenuItem value={1}>1 Player (Fast)</MenuItem>
                <MenuItem value={2}>2 Players</MenuItem>
                <MenuItem value={3}>3 Players (Standard)</MenuItem>
                <MenuItem value={5}>5 Players (Full Slate)</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Attempts Per Player</InputLabel>
              <Select value={numAttempts} label="Attempts Per Player" onChange={(e: any) => setNumAttempts(e.target.value)}>
                <MenuItem value={1}>1 Attempt (temp=default)</MenuItem>
                <MenuItem value={2}>2 Attempts (temp=0.7)</MenuItem>
                <MenuItem value={3}>3 Attempts (temp=1.0 consistency)</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={4}>
            <FormControlLabel
              control={<Checkbox checked={useBibleStyle} onChange={(e) => setUseBibleStyle(e.target.checked)} color="primary" />}
              label={
                <Typography variant="body2">
                  Use Bible-Style Prompt (Explicit URLs + Anti-patterns)
                </Typography>
              }
            />
          </Grid>

          <Grid item xs={12} sm={2}>
            <Button
              variant="contained"
              color="primary"
              fullWidth
              disabled={running}
              onClick={handleRunAudit}
              startIcon={<Play size={16} />}
              sx={{ py: 1, fontWeight: 700 }}
            >
              {running ? "Auditing..." : "Run Audit"}
            </Button>
          </Grid>
        </Grid>

        {running && (
          <Box sx={{ mt: 2.5 }}>
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 0.5 }}>
              {progressText}
            </Typography>
            <LinearProgress variant="determinate" value={progress} color="primary" sx={{ height: 6, borderRadius: 3 }} />
          </Box>
        )}
      </Card>

      {error && (
        <Alert severity="error">
          {error}
        </Alert>
      )}

      {/* Results Section */}
      {auditData && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {/* Summary Metric Tiles */}
          <Grid container spacing={2}>
            <Grid item xs={12} sm={4}>
              <Card sx={{ p: 2.5, bgcolor: "background.paper", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                <Typography variant="caption" sx={{ color: "text.secondary", textTransform: "uppercase", fontWeight: 700 }}>
                  Avg Field-Fill Rate
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 800, color: "success.main", fontFamily: "monospace", mt: 0.5 }}>
                  {(auditData.summary.avg_field_fill_rate * 100).toFixed(1)}%
                </Typography>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  Percentage of required scoring fields populated
                </Typography>
              </Card>
            </Grid>

            <Grid item xs={12} sm={4}>
              <Card sx={{ p: 2.5, bgcolor: "background.paper", border: "1px solid rgba(6, 182, 212, 0.3)" }}>
                <Typography variant="caption" sx={{ color: "text.secondary", textTransform: "uppercase", fontWeight: 700 }}>
                  Avg Source-URL Presence
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 800, color: "primary.main", fontFamily: "monospace", mt: 0.5 }}>
                  {(auditData.summary.avg_source_url_presence * 100).toFixed(1)}%
                </Typography>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  Grounded web citations attached
                </Typography>
              </Card>
            </Grid>

            <Grid item xs={12} sm={4}>
              <Card sx={{ p: 2.5, bgcolor: "background.paper", border: "1px solid rgba(245, 158, 11, 0.3)" }}>
                <Typography variant="caption" sx={{ color: "text.secondary", textTransform: "uppercase", fontWeight: 700 }}>
                  Avg Critical-Null Rate
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 800, color: "warning.main", fontFamily: "monospace", mt: 0.5 }}>
                  {(auditData.summary.avg_critical_null_rate * 100).toFixed(1)}%
                </Typography>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  Missing critical line or availability metrics
                </Typography>
              </Card>
            </Grid>
          </Grid>

          {/* Per-Player Results Grid */}
          <Card sx={{ p: 2.5, bgcolor: "background.paper" }}>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
              Per-Player Quality Metrics
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700 }}>Player</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Fill Rate</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Source URLs</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Critical Nulls</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Confidence</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Consistency (CV)</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {auditData.players.map((p: any) => (
                    <TableRow key={p.player}>
                      <TableCell sx={{ fontWeight: 600 }}>{p.player}</TableCell>
                      <TableCell sx={{ color: "success.main", fontFamily: "monospace" }}>{(p.fill_rate * 100).toFixed(0)}%</TableCell>
                      <TableCell sx={{ fontFamily: "monospace" }}>{(p.source_urls_presence * 100).toFixed(0)}%</TableCell>
                      <TableCell sx={{ fontFamily: "monospace" }}>{p.critical_nulls}</TableCell>
                      <TableCell sx={{ fontWeight: 700, color: "primary.light" }}>{p.confidence_score}</TableCell>
                      <TableCell sx={{ fontFamily: "monospace" }}>{p.consistency_cv.toFixed(3)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Card>

          {/* Observed Sources & Bible Checklist */}
          <Grid container spacing={3}>
            {/* Grounding Sources Observed */}
            <Grid item xs={12} md={6}>
              <Card sx={{ p: 2.5, bgcolor: "background.paper" }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
                  <Globe size={18} color="#06B6D4" />
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>Grounding Sources Observed</Typography>
                </Box>
                <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                  {auditData.sources.map((s: any) => (
                    <Box key={s.domain} sx={{ display: "flex", justifyContent: "space-between", py: 0.5, borderBottom: "1px solid #1E293B" }}>
                      <Typography variant="body2" sx={{ fontFamily: "monospace" }}>{s.domain}</Typography>
                      <Chip label={`${s.count} hits`} size="small" sx={{ height: 20, fontSize: "0.7rem" }} />
                    </Box>
                  ))}
                </Box>
              </Card>
            </Grid>

            {/* Bible Expected Sources */}
            <Grid item xs={12} md={6}>
              <Card sx={{ p: 2.5, bgcolor: "background.paper" }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
                  <BookOpen size={18} color="#10B981" />
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>Bible Expected Sources Verification</Typography>
                </Box>
                <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                  {auditData.bible_expected.map((b: any) => (
                    <Box key={b.source} sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", py: 0.5, borderBottom: "1px solid #1E293B" }}>
                      <Typography variant="body2" sx={{ fontFamily: "monospace" }}>{b.source}</Typography>
                      {b.present ? (
                        <Chip icon={<CheckCircle2 size={12} color="#10B981" />} label="PRESENT" size="small" sx={{ bgcolor: "rgba(16, 185, 129, 0.15)", color: "success.main", fontWeight: 700, height: 22 }} />
                      ) : (
                        <Chip icon={<XCircle size={12} color="#F43F5E" />} label="MISSING" size="small" sx={{ bgcolor: "rgba(244, 63, 94, 0.15)", color: "error.main", fontWeight: 700, height: 22 }} />
                      )}
                    </Box>
                  ))}
                </Box>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}
    </Box>
  );
};
