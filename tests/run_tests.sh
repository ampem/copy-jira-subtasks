#!/usr/bin/env bash
# Run all test scenarios against the mock Jira server.
# Expected to execute INSIDE the app container (JIRA_URL and JIRA_TOKEN already set).

set -euo pipefail

JIRA_URL="${JIRA_URL:-http://mock-jira:8080}"
TOKEN="${JIRA_API_TOKEN:-test-token}"
PASS=0
FAIL=0

_run() {
    local desc="$1"; shift
    echo ""
    echo "━━━ $desc ━━━"
    if "$@"; then
        echo "✓ PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "✗ FAIL: $desc (exit $?)"
        FAIL=$((FAIL + 1))
    fi
}

_expect_exit() {
    local expected="$1"; shift
    local desc="$1"; shift
    echo ""
    echo "━━━ $desc ━━━"
    set +e
    "$@"
    local actual=$?
    set -e
    if [ "$actual" -eq "$expected" ]; then
        echo "✓ PASS: $desc (exit $actual)"
        PASS=$((PASS + 1))
    else
        echo "✗ FAIL: $desc — expected exit $expected, got $actual"
        FAIL=$((FAIL + 1))
    fi
}

reset_mock() {
    curl -sf -X DELETE "$JIRA_URL/admin/reset" > /dev/null
}

created_count() {
    curl -sf "$JIRA_URL/admin/created" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"
}

# ---------------------------------------------------------------------------

reset_mock

_run "copy all subtasks (no filter, auto-confirm)" \
    python copy_subtasks.py \
        --url "$JIRA_URL" --token "$TOKEN" \
        --source PROJ-1 --target PROJ-2 \
        --yes

echo "  → Created: $(created_count) issues"

# ---------------------------------------------------------------------------

reset_mock

_run "filter-include: only Backend subtasks" \
    python copy_subtasks.py \
        --url "$JIRA_URL" --token "$TOKEN" \
        --source PROJ-1 --target PROJ-2 \
        --filter-include "^Backend" \
        --yes

count=$(created_count)
echo "  → Created: $count issues (expected 2)"
[ "$count" -eq 2 ] || { echo "  ✗ wrong count"; PASS=$((PASS-1)); FAIL=$((FAIL+1)); }

# ---------------------------------------------------------------------------

reset_mock

_run "filter-exclude: skip Frontend subtasks" \
    python copy_subtasks.py \
        --url "$JIRA_URL" --token "$TOKEN" \
        --source PROJ-1 --target PROJ-2 \
        --filter-exclude "^Frontend" \
        --yes

count=$(created_count)
echo "  → Created: $count issues (expected 3)"
[ "$count" -eq 3 ] || { echo "  ✗ wrong count"; PASS=$((PASS-1)); FAIL=$((FAIL+1)); }

# ---------------------------------------------------------------------------

reset_mock

_run "copy with description and assignee" \
    python copy_subtasks.py \
        --url "$JIRA_URL" --token "$TOKEN" \
        --source PROJ-1 --target PROJ-2 \
        --filter-include "^Backend" \
        --copy-description --copy-assignee \
        --yes

# ---------------------------------------------------------------------------

reset_mock

_expect_exit 1 "partial failure captured in --failed-output" \
    python copy_subtasks.py \
        --url "$JIRA_URL" --token "$TOKEN" \
        --source PROJ-1 --target PROJ-2 \
        --yes \
        --failed-output /tmp/failed.tsv

if [ -s /tmp/failed.tsv ]; then
    echo "  → Failed TSV contents:"
    cat /tmp/failed.tsv | sed 's/^/    /'
else
    echo "  ✗ expected /tmp/failed.tsv to be non-empty"
    PASS=$((PASS-1)); FAIL=$((FAIL+1))
fi

# ---------------------------------------------------------------------------

_expect_exit 1 "missing required --source argument" \
    python copy_subtasks.py --url "$JIRA_URL" --token "$TOKEN" --target PROJ-2

# ---------------------------------------------------------------------------

_expect_exit 1 "non-existent source issue returns error" \
    python copy_subtasks.py \
        --url "$JIRA_URL" --token "$TOKEN" \
        --source PROJ-999 --target PROJ-2 \
        --yes

# ---------------------------------------------------------------------------

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results: $PASS passed, $FAIL failed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
[ "$FAIL" -eq 0 ]
