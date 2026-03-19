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
BRANCH_NAME="gardener/intent-audit-${DATE_STAMP}"
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

# ─── Write prompt files ───────────────────────────────────────────
AUDIT_PROMPT_FILE="$(mktemp)"
FIX_PROMPT_FILE="$(mktemp)"
trap 'rm -f "$AUDIT_PROMPT_FILE" "$FIX_PROMPT_FILE"' EXIT

cat > "$AUDIT_PROMPT_FILE" << 'PROMPT_EOF'
You are the CivicLens Gardener — an autonomous maintenance agent responsible for
keeping this repository aligned with its stated design intent.

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
             "type": "missing_code|stale_status|unlinked_spec|missing_test|broken_reference|security",
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

6. Security threat model — Analyze the codebase for security concerns:
   a. API route protection: Are all API routes properly authenticated/rate-limited?
      Check src/app/api/ for missing auth checks, open endpoints, or missing input validation.
   b. Database security: Are RLS policies in place? Check supabase/migrations/ for
      row-level security on all tables. Verify anon role has minimal permissions.
   c. Injection vectors: Check for unsanitized user input in SQL queries, shell commands,
      or HTML rendering. Look for template literal SQL, dangerouslySetInnerHTML, exec/spawn.
   d. Secret exposure: Verify no API keys, tokens, or credentials are hardcoded in source.
      Check that all secrets flow through environment variables.
   e. Dependency risk: Note any known-vulnerable or unmaintained dependencies.
   f. Data flow trust boundaries: Trace user input from chat → API → RAG → LLM → response.
      Identify where prompt injection, data exfiltration, or context manipulation could occur.
   g. CORS/CSP: Check Next.js config for security headers (Content-Security-Policy,
      X-Frame-Options, X-Content-Type-Options).

   Add a "security" section to the JSON report:
   {
     "security": {
       "threat_level": "low|medium|high|critical",
       "findings": [
         {
           "category": "auth|rls|injection|secrets|dependencies|headers|prompt_injection",
           "severity": "critical|high|medium|low",
           "location": "file:line",
           "detail": "Description",
           "recommendation": "Fix"
         }
       ]
     }
   }

7. Assess overall state goal achievement — Evaluate whether the project is on track
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

cat > "$FIX_PROMPT_FILE" << 'FIX_EOF'
You are the CivicLens Gardener continuing from an audit. The audit report is at
.gardener-report.json. Read it now.

## Your Mandate — Fix Phase

Based on the audit findings, make targeted improvements:

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

- Only make changes that are clearly correct and low-risk.
- Prefer documentation accuracy over code changes.
- Never delete code or remove features.
- Never modify test expectations to make them pass — fix the code instead.
- Limit total changes to what's reviewable in a single PR (<500 lines diff).
- After making changes, provide a clear commit message and summary.

## Start

Read .gardener-report.json and begin making improvements.
FIX_EOF

# ─── Run the audit ─────────────────────────────────────────────────
echo "Gardener: Running intent audit..."

AUDIT_PROMPT="$(cat "$AUDIT_PROMPT_FILE")"
claude -p "$AUDIT_PROMPT" \
  --output-format text \
  --max-turns 30 \
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

# Check for drift before doing work
DRIFT_COUNT="$(python3 -c "
import json
r = json.load(open('$REPORT_FILE'))
print(sum(1 for a in r.get('arrows', []) if a.get('drift_detected')))
" 2>/dev/null || echo "0")"

if [ "$DRIFT_COUNT" = "0" ]; then
  echo "No drift detected. Nothing to fix."
  exit 0
fi

# Create branch
git checkout -b "$BRANCH_NAME"

# Run the fix agent
FIX_PROMPT="$(cat "$FIX_PROMPT_FILE")"
claude -p "$FIX_PROMPT" \
  --output-format text \
  --max-turns 20 \
  --allowedTools "Read,Glob,Grep,Write,Edit,Bash(cat:*),Bash(wc:*),Bash(find:*),Bash(git:status),Bash(git:diff),Bash(git:add)" \
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
  --label "gardener" \
  --base dev

echo "Gardener: PR created successfully."
