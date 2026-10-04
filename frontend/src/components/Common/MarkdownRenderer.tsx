import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Box, Typography, Link } from "@mui/material";

interface MarkdownRendererProps {
  content?: string | null;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  if (!content) return null;

  return (
    <Box
      sx={{
        color: "text.primary",
        fontSize: "0.95rem",
        lineHeight: 1.7,
        "& h1, & h2, & h3, & h4, & h5, & h6": {
          fontWeight: 700,
          color: "#F8FAFC",
          mt: 2.5,
          mb: 1.5,
          letterSpacing: "-0.01em",
        },
        "& h1": { fontSize: "1.75rem", borderBottom: "1px solid rgba(255,255,255,0.1)", pb: 1 },
        "& h2": { fontSize: "1.4rem", color: "primary.main" },
        "& h3": { fontSize: "1.2rem" },
        "& h4": { fontSize: "1.05rem" },
        "& p": { mb: 1.5 },
        "& ul, & ol": { pl: 3, mb: 1.5 },
        "& li": { mb: 0.5 },
        "& a": {
          color: "primary.main",
          textDecoration: "none",
          fontWeight: 600,
          "&:hover": { textDecoration: "underline" },
        },
        "& blockquote": {
          borderLeft: "4px solid #06B6D4",
          pl: 2,
          py: 0.5,
          my: 1.5,
          bgcolor: "rgba(6, 182, 212, 0.05)",
          borderRadius: "0 4px 4px 0",
          fontStyle: "italic",
        },
        "& code": {
          fontFamily: "'JetBrains Mono', monospace",
          bgcolor: "rgba(0, 0, 0, 0.35)",
          px: 0.8,
          py: 0.3,
          borderRadius: "4px",
          fontSize: "0.85em",
          color: "#38BDF8",
        },
        "& pre": {
          bgcolor: "#070B14",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: "8px",
          p: 2,
          overflowX: "auto",
          my: 2,
          "& code": {
            bgcolor: "transparent",
            p: 0,
            color: "#E2E8F0",
          },
        },
        "& table": {
          width: "100%",
          borderCollapse: "collapse",
          my: 2,
          borderRadius: "8px",
          overflow: "hidden",
          border: "1px solid rgba(255, 255, 255, 0.1)",
        },
        "& th": {
          bgcolor: "rgba(6, 182, 212, 0.15)",
          color: "#FFF",
          fontWeight: 700,
          textAlign: "left",
          p: 1.5,
          borderBottom: "1px solid rgba(255, 255, 255, 0.15)",
          fontSize: "0.85rem",
          textTransform: "uppercase",
        },
        "& td": {
          p: 1.5,
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
          fontSize: "0.9rem",
        },
        "& tr:hover td": {
          bgcolor: "rgba(255, 255, 255, 0.03)",
        },
        "& hr": {
          border: "none",
          borderTop: "1px solid rgba(255, 255, 255, 0.1)",
          my: 3,
        },
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, ...props }) => (
            <Link {...props} target="_blank" rel="noopener noreferrer" />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </Box>
  );
};
