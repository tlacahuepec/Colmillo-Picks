import React from "react";
import {
  Box,
  Typography,
  Chip,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
} from "@mui/material";
import {
  ChevronDown,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  ExternalLink,
} from "lucide-react";
import { AvailabilityBadge, SlateRankedCandidate } from "../../api/types";

export interface SlateCandidateCardProps {
  candidate: SlateRankedCandidate;
  badge?: AvailabilityBadge;
}

function formatKickoffLocal(kickoffUtc?: string | null): string {
  if (!kickoffUtc) return "—";
  try {
    const dt = new Date(kickoffUtc);
    return dt.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return kickoffUtc;
  }
}

function confidenceColor(conf: string | number): "success" | "warning" | "error" | "default" {
  const c = String(conf).toLowerCase();
  if (c === "high") return "success";
  if (c === "medium") return "warning";
  if (c === "low") return "error";
  return "default";
}

export const SlateCandidateCard: React.FC<SlateCandidateCardProps> = ({ candidate, badge }) => {
  const player = candidate.subject_name || candidate.player || "Unknown";
  const market = candidate.market || "Unknown";

  const home = candidate.source_match?.home_team;
  const away = candidate.source_match?.away_team;
  const kickoff = formatKickoffLocal(candidate.source_match?.kickoff_utc);
  const matchStr = home && away ? `${home} vs ${away} — ${kickoff}` : "";

  // Availability badge classification
  let badgeSeverity: "success" | "warning" | "error" | "default" = "default";
  let badgeLabel = "Unknown";
  let badgeIcon = <HelpCircle size={12} color="#94A3B8" />;
  let platformLineText: string | null = null;

  if (badge) {
    const isAvail = badge.status === "available";
    const isLineDiff =
      badge.status === "available" &&
      badge.platform_line != null &&
      candidate.line != null &&
      Math.abs(badge.platform_line - candidate.line) > 0.01;
    const isUnavail = badge.status === "unavailable";

    if (isLineDiff) {
      badgeSeverity = "warning";
      badgeLabel = "Line Differs";
      badgeIcon = <AlertTriangle size={12} color="#F59E0B" />;
      platformLineText = `Platform line: ${badge.platform_line}`;
    } else if (isAvail) {
      badgeSeverity = "success";
      badgeLabel = "Available";
      badgeIcon = <CheckCircle2 size={12} color="#10B981" />;
      if (badge.platform_line != null) {
        platformLineText = `Line: ${badge.platform_line}`;
      }
    } else if (isUnavail) {
      badgeSeverity = "error";
      badgeLabel = "Not Available";
      badgeIcon = <XCircle size={12} color="#EF4444" />;
    }
  }

  return (
    <Paper
      elevation={0}
      data-testid={`candidate-card-${candidate.rank}`}
      sx={{
        p: 2,
        bgcolor: "rgba(0,0,0,0.25)",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: "8px",
        display: "flex",
        flexDirection: "column",
        gap: 1.5,
        "&:hover": { borderColor: "rgba(6, 182, 212, 0.4)" },
      }}
    >
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 1 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <Typography variant="h6" sx={{ fontWeight: 800, color: "#06B6D4", minWidth: 36 }}>
            #{candidate.rank}
          </Typography>
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, color: "#FFF" }}>
              {player} — {market} {candidate.line != null ? candidate.line : ""} {candidate.direction || ""}
            </Typography>
            {matchStr && (
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                {matchStr}
              </Typography>
            )}
          </Box>
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <Box sx={{ textAlign: "right" }}>
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
              Score
            </Typography>
            <Typography variant="subtitle2" sx={{ fontWeight: 800, color: "#06B6D4" }}>
              {candidate.normalized_score?.toFixed(0)}
            </Typography>
          </Box>

          <Chip
            label={String(candidate.confidence)}
            size="small"
            color={confidenceColor(candidate.confidence)}
            sx={{ fontWeight: 700, textTransform: "uppercase", fontSize: "0.68rem" }}
          />

          {/* Availability Status Badge */}
          {badge && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.8 }}>
              <Chip
                icon={badgeIcon}
                label={badgeLabel}
                size="small"
                variant="outlined"
                color={badgeSeverity}
                sx={{ fontWeight: 700, fontSize: "0.68rem" }}
              />
              {platformLineText && (
                <Chip
                  label={platformLineText}
                  size="small"
                  sx={{
                    bgcolor: "rgba(255,255,255,0.06)",
                    fontSize: "0.68rem",
                    height: 20,
                  }}
                />
              )}
              {badge.url && (
                <Button
                  component="a"
                  href={badge.url}
                  target="_blank"
                  rel="noreferrer"
                  size="small"
                  sx={{ minWidth: 32, p: 0.5 }}
                >
                  <ExternalLink size={14} />
                </Button>
              )}
            </Box>
          )}
        </Box>
      </Box>

      {/* Risk Flags */}
      {candidate.risk_flags && candidate.risk_flags.length > 0 && (
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          {candidate.risk_flags.map((flag, fIdx) => (
            <Chip
              key={fIdx}
              label={flag}
              size="small"
              sx={{
                bgcolor: "rgba(245, 158, 11, 0.1)",
                color: "#F59E0B",
                borderColor: "rgba(245, 158, 11, 0.3)",
                border: "1px solid",
                fontSize: "0.68rem",
                height: 20,
              }}
            />
          ))}
        </Box>
      )}

      {/* Source pick detail expander */}
      {candidate.source_pick && (
        <Accordion sx={{ bgcolor: "transparent", boxShadow: "none", "&:before": { display: "none" } }}>
          <AccordionSummary sx={{ p: 0, minHeight: 32 }} expandIcon={<ChevronDown size={14} color="#94A3B8" />}>
            <Typography variant="caption" sx={{ color: "primary.main", fontWeight: 700 }}>
              Details: {player} — {market}
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ p: 1.5, bgcolor: "rgba(0,0,0,0.3)", borderRadius: "6px" }}>
            {candidate.source_pick.offer && (
              <Box sx={{ mb: 1 }}>
                <Typography variant="body2" sx={{ fontSize: "0.8rem", mb: 0.3 }}>
                  <strong>Sportsbook:</strong> {candidate.source_pick.offer.sportsbook} · Decimal odds:{" "}
                  {candidate.source_pick.offer.odds_decimal} · Observed: {candidate.source_pick.offer.observed_at}
                </Typography>
                {candidate.source_pick.offer.source_url && (
                  <Button
                    component="a"
                    href={candidate.source_pick.offer.source_url}
                    target="_blank"
                    rel="noreferrer"
                    size="small"
                    endIcon={<ExternalLink size={12} />}
                    sx={{ fontSize: "0.75rem", p: 0, minWidth: "auto", textTransform: "none", color: "primary.main" }}
                  >
                    Sportsbook source
                  </Button>
                )}
              </Box>
            )}

            {candidate.source_pick.score != null && (
              <Typography variant="body2" sx={{ fontSize: "0.8rem", mb: 0.5 }}>
                <strong>Score:</strong> {candidate.source_pick.score}
              </Typography>
            )}

            {/* NFL Explainability & Contributing Factors */}
            {candidate.source_pick.explainability && (
              <Box sx={{ mb: 1 }}>
                {candidate.source_pick.explainability.rationale && (
                  <Typography variant="body2" sx={{ fontSize: "0.8rem", mb: 0.5, color: "text.primary" }}>
                    {candidate.source_pick.explainability.rationale}
                  </Typography>
                )}
                {candidate.source_pick.explainability.top_contributing_factors && candidate.source_pick.explainability.top_contributing_factors.length > 0 && (
                  <Box sx={{ mt: 0.5 }}>
                    <Typography variant="caption" sx={{ color: "primary.main", fontWeight: 700, display: "block" }}>
                      Top Contributing Factors:
                    </Typography>
                    <Box component="ul" sx={{ m: 0, pl: 2 }}>
                      {candidate.source_pick.explainability.top_contributing_factors.map((f: any, i: number) => (
                        <li key={i} style={{ fontSize: "0.75rem", color: "#CBD5E1" }}>
                          {f.factor}: {typeof f.score === "number" ? f.score.toFixed(2) : f.score} (weight {typeof f.weight === "number" ? f.weight.toFixed(2) : f.weight})
                        </li>
                      ))}
                    </Box>
                  </Box>
                )}
              </Box>
            )}

            {candidate.source_pick.llm_rationale && (
              <Typography variant="body2" sx={{ fontSize: "0.8rem", color: "text.secondary", mb: 0.5 }}>
                <strong>Reasoning:</strong> {candidate.source_pick.llm_rationale}
              </Typography>
            )}

            {candidate.source_pick.factors && typeof candidate.source_pick.factors === "object" && (
              <Typography variant="body2" sx={{ fontSize: "0.8rem", color: "text.secondary" }}>
                <strong>Factors:</strong> {Object.entries(candidate.source_pick.factors).map(([k, v]) => `${k}: ${v}`).join(", ")}
              </Typography>
            )}
          </AccordionDetails>
        </Accordion>
      )}
    </Paper>
  );
};
