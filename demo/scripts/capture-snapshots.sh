#!/usr/bin/env bash
# Re-capture the static demo data from a running PACT backend.
#
# The demo site has no backend — it serves these JSON snapshots from
# demo/public/data/. Run this whenever you want the demo to reflect newer
# backend data. Requires the backend running locally (default :8000).
#
#   cd backend && uvicorn app.main:app --port 8000   # in another terminal
#   ./demo/scripts/capture-snapshots.sh
#
set -euo pipefail

B="${PACT_BACKEND:-http://localhost:8000}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/public/data"

echo "Capturing from $B -> $DIR"
mkdir -p "$DIR/runs"

curl -fsS "$B/scenarios"                  > "$DIR/scenarios.json"
curl -fsS "$B/runs"                       > "$DIR/runs.json"
curl -fsS "$B/dashboard/overview"         > "$DIR/dashboard-overview.json"
curl -fsS "$B/dashboard/agents"           > "$DIR/dashboard-agents.json"
curl -fsS "$B/dashboard/blocked-actions"  > "$DIR/dashboard-blocked-actions.json"

ids=$(python3 -c "import json;print(' '.join(r['run_id'] for r in json.load(open('$DIR/runs.json'))))")
for id in $ids; do
  mkdir -p "$DIR/runs/$id"
  curl -fsS "$B/runs/$id"                > "$DIR/runs/$id/detail.json"
  curl -fsS "$B/runs/$id/replay"         > "$DIR/runs/$id/replay.json"
  curl -fsS "$B/runs/$id/ledger/verify"  > "$DIR/runs/$id/ledger-verify.json"
done

echo "Captured $(echo "$ids" | wc -w) runs, $(find "$DIR" -name '*.json' | wc -l) JSON files."
