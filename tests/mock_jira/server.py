#!/usr/bin/env python3
"""Minimal Jira REST API mock for testing copy_subtasks.py."""

import json
import os
import uuid
from flask import Flask, jsonify, request, abort

app = Flask(__name__)

# ---------------------------------------------------------------------------
# In-memory state — seeded from fixtures files at startup
# ---------------------------------------------------------------------------

ISSUES: dict[str, dict] = {}   # key -> full issue dict
CREATED: list[dict] = []       # log of POST /rest/api/2/issue calls

FIXTURES_DIR = os.environ.get("FIXTURES_DIR", "/fixtures")


def _load_fixtures():
    if not os.path.isdir(FIXTURES_DIR):
        return
    for fname in os.listdir(FIXTURES_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(FIXTURES_DIR, fname)
        with open(path) as fh:
            data = json.load(fh)
        key = data.get("key")
        if key:
            ISSUES[key] = data
            app.logger.info("Loaded fixture: %s", key)


_load_fixtures()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/rest/api/2/issue/<key>")
def get_issue(key):
    if key not in ISSUES:
        abort(404, description=f"Issue {key} not found")
    return jsonify(ISSUES[key])


@app.post("/rest/api/2/issue")
def create_issue():
    body = request.get_json(force=True)
    fields = body.get("fields", {})
    summary = fields.get("summary", "")
    parent = fields.get("parent", {}).get("key", "")
    project = fields.get("project", {}).get("key", "TEST")

    # Reject if summary is empty (simulate validation error)
    if not summary:
        return jsonify({"errorMessages": [], "errors": {"summary": "Field required"}}), 400

    # Simulate a failure for summaries that contain the word FAIL
    if "FAIL" in summary.upper():
        return jsonify({"errorMessages": ["Simulated failure"], "errors": {}}), 422

    new_key = f"{project}-{1000 + len(CREATED) + 1}"
    new_issue = {
        "id": str(uuid.uuid4()),
        "key": new_key,
        "self": f"http://mock-jira:8080/rest/api/2/issue/{new_key}",
        "fields": {
            "summary": summary,
            "description": fields.get("description"),
            "status": {"name": "To Do"},
            "issuetype": fields.get("issuetype", {"name": "Sub-task"}),
            "parent": {"key": parent},
            "project": {"key": project},
            "priority": fields.get("priority"),
            "assignee": fields.get("assignee"),
        },
    }
    ISSUES[new_key] = new_issue
    CREATED.append(new_issue)
    return jsonify({"id": new_issue["id"], "key": new_key, "self": new_issue["self"]}), 201


@app.get("/admin/created")
def list_created():
    """Test helper — returns all issues created this session."""
    return jsonify(CREATED)


@app.delete("/admin/reset")
def reset():
    """Test helper — clears created issues and reloads fixtures."""
    CREATED.clear()
    ISSUES.clear()
    _load_fixtures()
    return jsonify({"status": "reset"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
