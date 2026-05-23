#!/usr/bin/env bash
# PACT Demo Script
# Runs all 6 demo scenarios and prints a summary.
# Usage: ./scripts/demo.sh

set -euo pipefail

BASE_URL="http://localhost:8000"
BACKEND_PID=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

cleanup() {
    if [ -n "$BACKEND_PID" ]; then
        echo -e "\n${YELLOW}Stopping backend (PID $BACKEND_PID)...${NC}"
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
        echo -e "${GREEN}Backend stopped.${NC}"
    fi
}
trap cleanup EXIT

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║     PACT — Provenance-Aware Capability Tokens       ║"
echo "║              Interactive Demo Script                 ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ──────────────────────────────────────────────
# Step 1: Check prerequisites
# ──────────────────────────────────────────────
echo -e "${BOLD}Step 1: Checking prerequisites...${NC}"

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Error: python3 is not installed.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Python $(python3 --version 2>&1 | awk '{print $2}')"

if ! command -v node &>/dev/null; then
    echo -e "${YELLOW}  ⚠ Node.js not found (optional for frontend).${NC}"
else
    echo -e "  ${GREEN}✓${NC} Node $(node --version)"
fi

# ──────────────────────────────────────────────
# Step 2: Install backend dependencies
# ──────────────────────────────────────────────
echo -e "\n${BOLD}Step 2: Installing backend dependencies...${NC}"

cd "$(dirname "$0")/../backend"

if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null
echo -e "  ${GREEN}✓${NC} Backend dependencies installed."

# ──────────────────────────────────────────────
# Step 3: Start backend server
# ──────────────────────────────────────────────
echo -e "\n${BOLD}Step 3: Starting backend server...${NC}"

# Remove old database to start clean
rm -f pact.db

uvicorn app.main:app --host 0.0.0.0 --port 8000 &>/dev/null &
BACKEND_PID=$!

# ──────────────────────────────────────────────
# Step 4: Wait for /health
# ──────────────────────────────────────────────
echo -e "  Waiting for server to start..."

MAX_WAIT=30
for i in $(seq 1 $MAX_WAIT); do
    if curl -sf "$BASE_URL/health" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Backend is running on port 8000."
        break
    fi
    if [ "$i" -eq "$MAX_WAIT" ]; then
        echo -e "  ${RED}Error: Backend did not start within ${MAX_WAIT}s.${NC}"
        exit 1
    fi
    sleep 1
done

# ──────────────────────────────────────────────
# Step 5: Run all 6 scenarios
# ──────────────────────────────────────────────
echo -e "\n${BOLD}Step 5: Running demo scenarios...${NC}"
echo ""

SCENARIOS=(
    "normal_email_summary"
    "malicious_email_injection"
    "fake_agent_identity"
    "expired_capability_token"
    "secret_exfiltration"
    "malicious_webpage"
)

declare -A RESULTS
declare -A SCORES
declare -A SEVERITIES

for scenario in "${SCENARIOS[@]}"; do
    echo -e "  ${CYAN}Running:${NC} $scenario"

    RESPONSE=$(curl -sf -X POST "$BASE_URL/scenarios/run/$scenario" 2>/dev/null || echo '{"error":"request failed"}')

    # Extract fields
    ALLOWED=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('allowed_actions','?'))" 2>/dev/null || echo "?")
    BLOCKED=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('blocked_actions','?'))" 2>/dev/null || echo "?")
    MAX_SCORE=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('max_risk_score','?'))" 2>/dev/null || echo "?")
    # Derive severity from max_risk_score (0-24=low, 25-59=medium, 60-89=high, 90-100=critical)
    risk=$MAX_SCORE
    if [ "$risk" -ge 90 ] 2>/dev/null; then severity="critical"
    elif [ "$risk" -ge 60 ] 2>/dev/null; then severity="high"
    elif [ "$risk" -ge 25 ] 2>/dev/null; then severity="medium"
    else severity="low"
    fi
    MAX_SEV="$severity"
    RUN_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('run_id','?'))" 2>/dev/null || echo "?")

    if [ "$BLOCKED" != "0" ] && [ "$BLOCKED" != "?" ]; then
        STATUS="${RED}BLOCKED${NC}"
    else
        STATUS="${GREEN}ALLOWED${NC}"
    fi

    RESULTS[$scenario]="$STATUS"
    SCORES[$scenario]="$MAX_SCORE"
    SEVERITIES[$scenario]="$MAX_SEV"

    echo -e "    → Allowed: $ALLOWED | Blocked: $BLOCKED | Risk: $MAX_SCORE | Severity: $MAX_SEV | Run: $RUN_ID"
    echo ""
done

# ──────────────────────────────────────────────
# Step 6: Print summary
# ──────────────────────────────────────────────
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  SCENARIO RESULTS SUMMARY${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
printf "  %-35s %-20s %-8s %-10s\n" "Scenario" "Result" "Risk" "Severity"
echo -e "  ─────────────────────────────────────────────────────────────────────"
for scenario in "${SCENARIOS[@]}"; do
    printf "  %-35b %-20b %-8s %-10s\n" "$scenario" "${RESULTS[$scenario]}" "${SCORES[$scenario]}" "${SEVERITIES[$scenario]}"
done
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""

# ──────────────────────────────────────────────
# Step 7: Fetch dashboard overview
# ──────────────────────────────────────────────
echo -e "${BOLD}Step 7: Dashboard Overview${NC}"
echo ""

DASHBOARD=$(curl -sf "$BASE_URL/dashboard/overview" 2>/dev/null || echo '{}')

echo "$DASHBOARD" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"  Total Runs:          {d.get('total_runs', '?')}\")
print(f\"  Total Actions:       {d.get('total_actions', '?')}\")
print(f\"  Allowed Actions:     {d.get('allowed_actions', '?')}\")
print(f\"  Blocked Actions:     {d.get('blocked_actions', '?')}\")
print(f\"  Critical Events:     {d.get('critical_events', '?')}\")
print(f\"  Max Risk Score:      {d.get('max_risk_score', '?')}\")

top_tools = d.get('top_attacked_tools', [])
if top_tools:
    print()
    print('  Top Attacked Tools:')
    for t in top_tools:
        print(f\"    - {t['tool']}: {t['count']} attempts\")

top_labels = d.get('top_provenance_sources', [])
if top_labels:
    print()
    print('  Top Provenance Sources:')
    for l in top_labels:
        print(f\"    - {l['source']}: {l['count']} occurrences\")
" 2>/dev/null || echo "  (Could not parse dashboard data)"

echo ""

# ──────────────────────────────────────────────
# Step 8: Verify a ledger
# ──────────────────────────────────────────────
echo -e "${BOLD}Step 8: Verifying ledger integrity...${NC}"

# Get the first run ID
FIRST_RUN=$(curl -sf "$BASE_URL/runs" 2>/dev/null | python3 -c "
import sys, json
runs = json.load(sys.stdin)
if runs:
    print(runs[0]['run_id'])
else:
    print('')
" 2>/dev/null || echo "")

if [ -n "$FIRST_RUN" ]; then
    VERIFY=$(curl -sf "$BASE_URL/runs/$FIRST_RUN/ledger/verify" 2>/dev/null || echo '{}')
    CHAIN_VALID=$(echo "$VERIFY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('valid','unknown'))" 2>/dev/null || echo "unknown")
    if [ "$CHAIN_VALID" = "True" ] || [ "$CHAIN_VALID" = "true" ]; then
        echo -e "  ${GREEN}✓${NC} Ledger chain is valid for run $FIRST_RUN"
    else
        echo -e "  ${RED}✗${NC} Ledger chain verification failed for run $FIRST_RUN"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} No runs found to verify."
fi

echo ""
echo -e "${GREEN}${BOLD}Demo complete!${NC}"
echo -e "  Backend API docs: ${CYAN}$BASE_URL/docs${NC}"
echo ""
