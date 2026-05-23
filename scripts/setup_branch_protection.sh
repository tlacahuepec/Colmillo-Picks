#!/usr/bin/env bash
# Apply branch protection rules for Colmillo-Picks.
#
# Usage:
#   bash scripts/setup_branch_protection.sh
#
# Prerequisites:
#   - gh CLI authenticated with admin access
#   - Repository: tlacahuepec/Colmillo-Picks
#
# This script configures:
#   - main: require PR, require CI checks (Lint, Tests, Build container images)
#   - dev: require PR, require basic CI checks (Lint, Tests)

set -euo pipefail

REPO="tlacahuepec/Colmillo-Picks"

echo "=== Configuring branch protection for $REPO ==="

# Create dev branch from main if it doesn't exist
if ! gh api "repos/$REPO/branches/dev" --silent 2>/dev/null; then
  echo "Creating 'dev' branch from main..."
  MAIN_SHA=$(gh api "repos/$REPO/git/ref/heads/main" --jq '.object.sha')
  gh api "repos/$REPO/git/refs" \
    -f ref="refs/heads/dev" \
    -f sha="$MAIN_SHA" --silent
  echo "Created 'dev' branch."
else
  echo "'dev' branch already exists."
fi

# Protect main branch
echo ""
echo "--- Protecting 'main' branch ---"
gh api "repos/$REPO/branches/main/protection" \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Lint", "Tests", "Build container images"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
echo "main branch protection applied."

# Protect dev branch
echo ""
echo "--- Protecting 'dev' branch ---"
gh api "repos/$REPO/branches/dev/protection" \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": false,
    "contexts": ["Lint", "Tests"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
echo "dev branch protection applied."

echo ""
echo "=== Done. Branch protection configured. ==="
echo ""
echo "Summary:"
echo "  main: PR required, 1 approval, CI checks (Lint + Tests + Docker Build)"
echo "  dev:  PR required, 1 approval, CI checks (Lint + Tests)"
