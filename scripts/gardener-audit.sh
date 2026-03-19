#!/usr/bin/env bash
# CivicLens Gardener — Agentic Intent Audit
#
# Uses Claude Code SDK to analyze the repository against its arrows of intent,
# detect drift between specs and implementation, and propose fixes via PR.
#
# Usage:
#   ./scripts/gardener-audit.sh              # Audit only (prints report)
#   ./scripts/gardener-audit.sh --fix        # Audit + create PR with fixes
#
# Required environment:
#   ANTHROPIC_API_KEY — Claude API key
#
# Optional environment:
#   GITHUB_TOKEN — For PR creation (auto-set in GitHub Actions)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FIX_MODE="${1:-}"
DATE_STAMP="$(date -u +'%Y-%m-%d')"
BRANCH_NAME="gardener-intent-audit-${DATE_STAMP}"
REPORT_FILE="${REPO_ROOT}/.gardener-report.json"
CONTEXT_FILE="${REPO_ROOT}/.gardener-context.md"

cd "$REPO_ROOT"

# ─── Preflight ─────────────────────────────────────────────────────
if ! command -v claude &>/dev/null; then
  echo "::error::Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
  exit 1
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "::error::ANTHROPIC_API_KEY is not set."
  exit 1
fi

# ─── Collect upstream health check results ─────────────────────────
LINT_RESULT="${GARDENER_LINT_RESULT:-unknown}"
PYLINT_RESULT="${GARDENER_PYLINT_RESULT:-unknown}"
BUILD_RESULT="${GARDENER_BUILD_RESULT:-unknown}"
TEST_RESULT="${GARDENER_TEST_RESULT:-unknown}"

HAS_FAILURES="false"
FAILURE_SUMMARY=""
if [ "$LINT_RESULT" = "failure" ]; then
  HAS_FAILURES="true"
  FAILURE_SUMMARY="${FAILURE_SUMMARY}
- LINT FAILED: Run 'npm run lint' and 'npx tsc --noEmit' to see errors. Fix lint and type errors in src/."
fi
if [ "$PYLINT_RESULT" = "failure" ]; then
  HAS_FAILURES="true"
  FAILURE_SUMMARY="${FAILURE_SUMMARY}
- PYTHON LINT FAILED: Run 'ruff check src/ tests/' to see errors. Fix ruff violations in Python code."
fi
if [ "$BUILD_RESULT" = "failure" ]; then
  HAS_FAILURES="true"
  FAILURE_SUMMARY="${FAILURE_SUMMARY}
- BUILD FAILED: Run 'npm run build' to see errors. Fix build-breaking issues in src/."
fi
if [ "$TEST_RESULT" = "failure" ]; then
  HAS_FAILURES="true"
  FAILURE_SUMMARY="${FAILURE_SUMMARY}
- TESTS FAILED: Run 'pytest tests/ -v --tb=short' to see failures. Fix failing tests by fixing the code (not the test expectations)."
fi

# ─── Write prompt files ───────────────────────────────────────────
AUDIT_PROMPT_FILE="$(mktemp)"
FIX_PROMPT_FILE="$(mktemp)"
trap 'rm -f "$AUDIT_PROMPT_FILE" "$FIX_PROMPT_FILE"' EXIT

cat > "$AUDIT_PROMPT_FILE" << PROMPT_EOF
You are the CivicLens Gardener — an autonomous maintenance agent responsible for
keeping this repository aligned with its stated design intent.

## Upstream Health Check Results

| Check | Result |
|-------|--------|
| Frontend Lint & TypeCheck | ${LINT_RESULT} |
| Python Lint (Ruff) | ${PYLINT_RESULT} |
| Next.js Build | ${BUILD_RESULT} |
| Python Tests | ${TEST_RESULT} |
$(if [ "$HAS_FAILURES" = "true" ]; then echo "
FAILURES DETECTED — These must be investigated and included in your report:
${FAILURE_SUMMARY}
"; fi)

## Context Recovery (Token Optimization)

FIRST, check if .gardener-context.md exists. If it does, read it — it contains
a condensed snapshot from your last audit run: which arrows were audited, what their
status was, which specs were implemented, and key findings. Use this to SKIP
re-analyzing unchanged areas and focus your effort on:
- Arrows whose code files have changed since the last audit (check git log)
- New specs or arrows that weren't in the previous context
- Previously flagged drift that may now be resolved

If .gardener-context.md does not exist, this is a fresh audit — analyze everything.

LAST, after completing your audit and writing the JSON report, also write/update
.gardener-context.md with a condensed snapshot for the next run. Format:

# Gardener Context — {date}
## Arrow Status Snapshot
(table of Arrow, Status, Drift, Last Audited)
## Implemented Specs (checked off)
(list of spec IDs that are implemented)
## Key Findings Carried Forward
(findings that weren't resolved)
## Files Hash (for change detection)
(output of: git log --oneline -1 -- docs/ src/ for quick staleness check)

This context file is committed to the repo so future runs can resume efficiently.

## Your Mandate

1. Read the arrows of intent — Start with docs/arrows/index.yaml to understand
   the project's arrow structure, dependencies, and status. Then read each arrow
   detail file referenced in the index.

2. Read the EARS specifications — Read every file in docs/specs/ to understand
   the granular requirements for each arrow.

3. Audit code against specs — For each arrow:
   a. Check if the code files listed in the arrow's "Code" section actually exist.
   b. Search for @spec annotations in the codebase and cross-reference them against
      the EARS spec IDs. Find specs that have code but aren't annotated, and annotations
      that reference non-existent specs.
   c. For implemented specs, verify the code actually fulfills the requirement (read the
      code, compare to spec language).
   d. Check if arrow status fields (status, drift) are accurate given current code state.

4. Detect drift — Identify gaps between intent and implementation:
   - Specs marked as active but with no corresponding code
   - Code that exists but doesn't match its spec
   - Arrow status that's stale (e.g., says MAPPED but code is partially implemented)
   - Missing test coverage for implemented specs
   - Files referenced in arrows that don't exist yet
   - @spec annotations in code that reference deferred or non-existent specs

5. Produce a JSON report — Output a JSON object to .gardener-report.json with this structure:
   {
     "date": "YYYY-MM-DD",
     "summary": "One paragraph overall assessment",
     "arrows": [
       {
         "name": "arrow-name",
         "declared_status": "MAPPED",
         "actual_status": "PARTIALLY_IMPLEMENTED",
         "drift_detected": true,
         "findings": [
           {
             "type": "missing_code|stale_status|unlinked_spec|missing_test|broken_reference",
             "severity": "high|medium|low",
             "spec_id": "DASH-VIEW-001",
             "detail": "Description of the finding",
             "recommendation": "What should be done"
           }
         ]
       }
     ],
     "stats": {
       "total_specs": 0,
       "implemented_specs": 0,
       "partially_implemented": 0,
       "not_started": 0,
       "coverage_pct": 0
     }
   }

6. Assess overall state goal achievement — Evaluate whether the project is on track
   to deliver its stated purpose: "Plain-language access to the laws that affect you."
   Consider: Is the data pipeline working? Is the chat functional? Is the dashboard
   useful? What's the biggest gap between current state and ideal state?

## Rules

- Be thorough but honest. Don't inflate findings.
- Every finding must reference a specific spec ID or file path.
- Distinguish between "not yet started" (expected for MAPPED arrows) and "drift"
  (code exists but diverges from spec, or status is wrong).
- Do NOT modify any code during the audit phase. Only read and report.
- Write the JSON report to .gardener-report.json in the repo root.
- Write/update .gardener-context.md with the condensed context snapshot for next run.
- After writing the report, print a human-readable summary to stdout.

## Start

Begin by reading docs/arrows/index.yaml, then systematically audit each arrow.
PROMPT_EOF

cat > "$FIX_PROMPT_FILE" << FIX_EOF
You are the CivicLens Gardener continuing from an audit. The audit report is at
.gardener-report.json. Read it now.

## Upstream Health Check Results

| Check | Result |
|-------|--------|
| Frontend Lint & TypeCheck | ${LINT_RESULT} |
| Python Lint (Ruff) | ${PYLINT_RESULT} |
| Next.js Build | ${BUILD_RESULT} |
| Python Tests | ${TEST_RESULT} |

## Your Mandate — Fix Phase

Priority order (fix the most critical issues first):

### Priority 1: Fix Failing Health Checks

If ANY upstream health check failed, this is your TOP PRIORITY. Before doing
anything else:

a. REPRODUCE the failure — run the failing command yourself to see the exact errors:
   - Lint failed: run 'npx next lint' and 'npx tsc --noEmit'
   - Python lint failed: run 'ruff check src/ tests/'
   - Build failed: run 'npx next build' (may need env vars — check .env.example)
   - Tests failed: run 'pytest tests/ -v --tb=short'

b. READ the error output carefully. Understand the root cause.

c. FIX the code that is causing the failure. Common patterns:
   - Type errors: fix the TypeScript types, add missing type annotations
   - Lint errors: fix the lint violations in the source code
   - Ruff errors: fix Python style/import issues
   - Test failures: fix the APPLICATION CODE so tests pass (never weaken tests)
   - Build failures: fix import errors, missing dependencies, config issues

d. RE-RUN the command to verify your fix actually works before moving on.

### Priority 2: Fix Drift (Intent Alignment)

After all health checks are green (or were already passing):

1. Update arrow drift fields — For each arrow where drift was detected, update
   docs/arrows/index.yaml to set the drift field with a concise description
   and update sampled to today's date.

2. Fix stale status — If an arrow's actual status differs from declared status
   (e.g., code partially exists but status says MAPPED), update the status field.

3. Add missing @spec annotations — If code implements a spec but lacks the
   @spec annotation, add it. Use the format:
   - Python: # @spec SPEC-ID-001
   - TypeScript: // @spec SPEC-ID-001

4. Check off implemented specs — In docs/specs/*.md, change - [ ] to - [x]
   for specs that the code verifiably implements.

5. Update arrow detail docs — If the "Key Findings" section says "None yet",
   add findings based on what exists in the code.

6. Propose small code improvements — If a spec is almost implemented but has
   a minor gap (e.g., missing legal disclaimer, missing null check), fix it.
   Do NOT attempt large features or major refactors.

## Rules

- ALWAYS fix failing health checks before addressing drift.
- Fix the code, not the tests — if a test fails, the code is wrong.
- Only make changes that are clearly correct and low-risk.
- Prefer documentation accuracy over code changes (for drift fixes).
- Never delete code or remove features.
- After fixing health checks, re-run the command to verify the fix.
- Limit total changes to what's reviewable in a single PR (<500 lines diff).
- After making changes, provide a clear commit message and summary.

## Start

Read .gardener-report.json and begin making improvements. If health checks
failed, start by reproducing and fixing those failures.
FIX_EOF

# ─── Run the audit ─────────────────────────────────────────────────
echo "Gardener: Running intent audit..."

AUDIT_PROMPT="$(cat "$AUDIT_PROMPT_FILE")"
claude -p "$AUDIT_PROMPT" \
  --output-format text \
  --max-turns 50 \
  --allowedTools "Read,Glob,Grep,Write,Bash(cat:*),Bash(wc:*),Bash(find:*)" \
  2>&1

if [ ! -f "$REPORT_FILE" ]; then
  echo "::warning::Audit completed but no report file generated."
  exit 0
fi

echo ""
echo "Audit report written to .gardener-report.json"
echo ""

# ─── Summarize for GitHub Actions ──────────────────────────────────
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "## Gardener Intent Audit — ${DATE_STAMP}"
    echo ""
    python3 "${SCRIPT_DIR}/gardener-summarize.py" "$REPORT_FILE"
  } >> "$GITHUB_STEP_SUMMARY"
fi

# ─── Fix mode: create branch and PR ───────────────────────────────
if [ "$FIX_MODE" != "--fix" ]; then
  echo "Audit complete. Run with --fix to create a PR with improvements."
  exit 0
fi

echo ""
echo "Gardener: Entering fix mode — creating improvements branch..."

# Check if there's work to do (drift or health check failures)
DRIFT_COUNT="$(python3 -c "
import json
r = json.load(open('$REPORT_FILE'))
print(sum(1 for a in r.get('arrows', []) if a.get('drift_detected')))
" 2>/dev/null || echo "0")"

if [ "$DRIFT_COUNT" = "0" ] && [ "$HAS_FAILURES" = "false" ]; then
  echo "No drift detected and all health checks passed. Nothing to fix."
  exit 0
fi

if [ "$HAS_FAILURES" = "true" ]; then
  echo "Health check failures detected — agent will attempt to fix them."
fi
if [ "$DRIFT_COUNT" != "0" ]; then
  echo "Intent drift detected in $DRIFT_COUNT arrows."
fi

# Create branch (append short hash if name already exists)
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME" 2>/dev/null || \
   git ls-remote --exit-code --heads origin "$BRANCH_NAME" >/dev/null 2>&1; then
  SHORT_HASH="$(git rev-parse --short HEAD)"
  BRANCH_NAME="${BRANCH_NAME}-${SHORT_HASH}"
  echo "Branch name collision — using $BRANCH_NAME"
fi
git checkout -b "$BRANCH_NAME"

# Run the fix agent
FIX_PROMPT="$(cat "$FIX_PROMPT_FILE")"
claude -p "$FIX_PROMPT" \
  --output-format text \
  --max-turns 50 \
  --allowedTools "Read,Glob,Grep,Write,Edit,Bash" \
  2>&1

# Check if there are changes
if git diff --quiet && git diff --cached --quiet; then
  echo "Fix agent made no changes."
  git checkout -
  git branch -D "$BRANCH_NAME"
  exit 0
fi

# Commit and push
git add -A
git commit -m "chore(gardener): intent audit fixes — ${DATE_STAMP}

Automated maintenance by the CivicLens Gardener agent:
- Updated arrow drift fields and status in index.yaml
- Added/fixed @spec annotations in source code
- Checked off implemented specs in docs/specs/
- Updated .gardener-context.md for next run token efficiency
- Minor code improvements for spec compliance

Co-Authored-By: CivicLens Gardener <noreply@github.com>"

git push origin "$BRANCH_NAME"

# Create PR
gh pr create \
  --title "Gardener: intent alignment fixes ${DATE_STAMP}" \
  --body "## Gardener Intent Audit

Automated PR from the CivicLens Gardener agent. This PR contains fixes
identified during the weekly intent audit.

### What the gardener checked
- Arrow status accuracy across all arrows with detected drift
- EARS spec coverage and @spec annotation alignment
- Code-to-intent coherence for implemented features
- Documentation accuracy (arrow docs, spec checklists)

### Changes made
See individual file diffs for details. All changes are low-risk documentation
and annotation updates, with minor code fixes where specs were almost met.

### Review guidance
- Verify drift field updates in docs/arrows/index.yaml are accurate
- Check that @spec annotations point to correct spec IDs
- Confirm spec checkbox updates in docs/specs/ match reality

---
Generated by CivicLens Gardener" \
  --label "gardener,maintenance" \
  --base main

echo "Gardener: PR created successfully."
