#!/usr/bin/env python3
"""Copy subtasks from one Jira issue to another."""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth


@dataclass
class JiraClient:
    base_url: str
    token: str
    email: Optional[str] = None

    def _auth(self):
        if self.email:
            return HTTPBasicAuth(self.email, self.token)
        return None

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if not self.email:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_issue(self, key: str) -> dict:
        url = f"{self.base_url}/rest/api/2/issue/{key}"
        resp = requests.get(url, headers=self._headers(), auth=self._auth())
        resp.raise_for_status()
        return resp.json()

    def create_issue(self, payload: dict) -> dict:
        url = f"{self.base_url}/rest/api/2/issue"
        resp = requests.post(url, headers=self._headers(), auth=self._auth(), json=payload)
        resp.raise_for_status()
        return resp.json()


@dataclass
class SubtaskSpec:
    key: str
    summary: str
    status: str
    description: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None


def fetch_subtasks(client: JiraClient, source_key: str) -> list[SubtaskSpec]:
    issue = client.get_issue(source_key)
    raw_subtasks = issue.get("fields", {}).get("subtasks", [])
    subtasks = []
    for st in raw_subtasks:
        key = st["key"]
        summary = st["fields"]["summary"]
        status = st["fields"]["status"]["name"]
        subtasks.append(SubtaskSpec(key=key, summary=summary, status=status))
    return subtasks


def fetch_subtask_details(client: JiraClient, specs: list[SubtaskSpec]) -> list[SubtaskSpec]:
    """Enrich subtask specs with description, priority, and assignee."""
    enriched = []
    for spec in specs:
        try:
            issue = client.get_issue(spec.key)
            fields = issue.get("fields", {})
            desc = fields.get("description")
            priority = fields.get("priority", {})
            priority_name = priority.get("name") if priority else None
            assignee = fields.get("assignee") or {}
            assignee_name = assignee.get("displayName") if assignee else None
            enriched.append(SubtaskSpec(
                key=spec.key,
                summary=spec.summary,
                status=spec.status,
                description=desc,
                priority=priority_name,
                assignee=assignee_name,
            ))
        except requests.HTTPError:
            enriched.append(spec)
    return enriched


def apply_filter(
    subtasks: list[SubtaskSpec],
    include_pattern: Optional[str],
    exclude_pattern: Optional[str],
) -> list[SubtaskSpec]:
    filtered = subtasks
    if include_pattern:
        rx = re.compile(include_pattern, re.IGNORECASE)
        filtered = [s for s in filtered if rx.search(s.summary)]
    if exclude_pattern:
        rx = re.compile(exclude_pattern, re.IGNORECASE)
        filtered = [s for s in filtered if not rx.search(s.summary)]
    return filtered


def get_project_key(issue_key: str) -> str:
    return issue_key.rsplit("-", 1)[0]


def print_review_table(
    source_key: str,
    target_key: str,
    all_subtasks: list[SubtaskSpec],
    selected: list[SubtaskSpec],
    copy_description: bool,
    copy_assignee: bool,
) -> None:
    skipped = [s for s in all_subtasks if s not in selected]

    print(f"\nSource issue : {source_key}  ({len(all_subtasks)} subtask(s) total)")
    print(f"Target issue : {target_key}")
    print()

    col_key  = max(len("SOURCE KEY"), max((len(s.key) for s in all_subtasks), default=0))
    col_sum  = max(len("SUMMARY"), max((len(s.summary) for s in all_subtasks), default=0))
    col_stat = max(len("STATUS"), max((len(s.status) for s in all_subtasks), default=0))

    header = f"  {'SOURCE KEY':<{col_key}}  {'SUMMARY':<{col_sum}}  {'STATUS':<{col_stat}}  ACTION"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for s in all_subtasks:
        action = "CREATE" if s in selected else "skip"
        print(f"  {s.key:<{col_key}}  {s.summary:<{col_sum}}  {s.status:<{col_stat}}  {action}")

    print()
    print(f"Will CREATE {len(selected)} subtask(s) under {target_key}:")
    extra = []
    if copy_description:
        extra.append("description")
    if copy_assignee:
        extra.append("assignee")
    fields_note = (", ".join(["summary"] + extra)) if extra else "summary only"
    print(f"  Fields copied: {fields_note}")


def build_create_payload(
    spec: SubtaskSpec,
    target_key: str,
    project_key: str,
    subtask_type_name: str,
    copy_description: bool,
    copy_assignee: bool,
) -> dict:
    payload: dict = {
        "fields": {
            "project": {"key": project_key},
            "parent": {"key": target_key},
            "issuetype": {"name": subtask_type_name},
            "summary": spec.summary,
        }
    }
    if copy_description and spec.description:
        payload["fields"]["description"] = spec.description
    if copy_assignee and spec.assignee:
        payload["fields"]["assignee"] = {"displayName": spec.assignee}
    return payload


def create_subtasks(
    client: JiraClient,
    selected: list[SubtaskSpec],
    target_key: str,
    project_key: str,
    subtask_type_name: str,
    copy_description: bool,
    copy_assignee: bool,
) -> tuple[list[dict], list[tuple[SubtaskSpec, str]]]:
    created = []
    failed = []
    for spec in selected:
        payload = build_create_payload(
            spec, target_key, project_key, subtask_type_name,
            copy_description, copy_assignee,
        )
        try:
            result = client.create_issue(payload)
            created.append({"source": spec.key, "new_key": result.get("key"), "summary": spec.summary})
            print(f"  Created {result.get('key')} <- {spec.key}: {spec.summary}")
        except requests.HTTPError as exc:
            reason = exc.response.text if exc.response is not None else str(exc)
            failed.append((spec, reason))
            print(f"  FAILED  {spec.key}: {spec.summary}  ({reason})", file=sys.stderr)
    return created, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy subtasks from one Jira issue to another.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables:
  JIRA_URL        Jira base URL (overridden by --url)
  JIRA_API_TOKEN  API token (overridden by --token)
  JIRA_EMAIL      Atlassian account email for Jira Cloud Basic Auth (overridden by --email)

Examples:
  # Jira Server / Data Center (Bearer token):
  copy_subtasks.py --url https://jira.example.com --token $JIRA_API_TOKEN --source PROJ-1 --target PROJ-2

  # Jira Cloud (Basic Auth):
  copy_subtasks.py --url https://your-domain.atlassian.net --email user@example.com --token $JIRA_API_TOKEN --source PROJ-1 --target PROJ-2

  copy_subtasks.py --source PROJ-1 --target PROJ-2 --filter-include "backend"
  copy_subtasks.py --source PROJ-1 --target PROJ-2 --filter-exclude "frontend|design"
""",
    )
    parser.add_argument("--url", default=os.environ.get("JIRA_URL"),
                        help="Jira base URL, e.g. https://jira.example.com")
    parser.add_argument("--email", default=os.environ.get("JIRA_EMAIL"),
                        help="Atlassian account email (Jira Cloud Basic Auth)")
    parser.add_argument("--token", default=os.environ.get("JIRA_API_TOKEN"),
                        help="API token (Bearer for Server/DC, Basic Auth for Cloud)")
    parser.add_argument("--source", required=True, metavar="ISSUE_KEY",
                        help="Source issue key (e.g. PROJ-123)")
    parser.add_argument("--target", required=True, metavar="ISSUE_KEY",
                        help="Target issue key (e.g. PROJ-456)")
    parser.add_argument("--filter-include", metavar="REGEX",
                        help="Only copy subtasks whose summary matches this regex")
    parser.add_argument("--filter-exclude", metavar="REGEX",
                        help="Skip subtasks whose summary matches this regex")
    parser.add_argument("--subtask-type", default="Sub-task",
                        help="Jira issue type name for subtasks (default: 'Sub-task')")
    parser.add_argument("--copy-description", action="store_true",
                        help="Also copy the description field")
    parser.add_argument("--copy-assignee", action="store_true",
                        help="Also copy the assignee field")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation prompt")
    parser.add_argument("--failed-output", metavar="FILE",
                        help="Write failed subtask keys/summaries to this file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.url:
        print("Error: Jira URL required (--url or JIRA_URL env var)", file=sys.stderr)
        return 1
    if not args.token:
        print("Error: API token required (--token or JIRA_API_TOKEN env var)", file=sys.stderr)
        return 1

    client = JiraClient(base_url=args.url.rstrip("/"), token=args.token, email=args.email)

    print(f"Fetching subtasks from {args.source}...")
    try:
        all_subtasks = fetch_subtasks(client, args.source)
    except requests.HTTPError as exc:
        print(f"Error fetching {args.source}: {exc}", file=sys.stderr)
        return 1

    if not all_subtasks:
        print(f"No subtasks found on {args.source}.")
        return 0

    selected = apply_filter(all_subtasks, args.filter_include, args.filter_exclude)

    if not selected:
        print("No subtasks match the filter. Nothing to do.")
        return 0

    if args.copy_description or args.copy_assignee:
        print(f"Fetching details for {len(selected)} subtask(s)...")
        selected = fetch_subtask_details(client, selected)
        # also refresh all_subtasks detail for display consistency
        non_selected_keys = {s.key for s in all_subtasks} - {s.key for s in selected}
        all_subtasks = selected + [s for s in all_subtasks if s.key in non_selected_keys]

    print(f"Fetching target issue {args.target}...")
    try:
        target_issue = client.get_issue(args.target)
    except requests.HTTPError as exc:
        print(f"Error fetching {args.target}: {exc}", file=sys.stderr)
        return 1

    project_key = target_issue["fields"]["project"]["key"]

    print_review_table(
        args.source, args.target,
        all_subtasks, selected,
        args.copy_description, args.copy_assignee,
    )

    if not args.yes:
        answer = input("\nProceed? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 0

    print(f"\nCreating {len(selected)} subtask(s) under {args.target}...")
    created, failed = create_subtasks(
        client, selected, args.target, project_key,
        args.subtask_type, args.copy_description, args.copy_assignee,
    )

    print(f"\nDone: {len(created)} created, {len(failed)} failed.")

    if failed:
        print("\nFailed subtasks:")
        for spec, reason in failed:
            print(f"  {spec.key}: {spec.summary}")
            print(f"    Reason: {reason}")
        if args.failed_output:
            with open(args.failed_output, "w") as fh:
                for spec, reason in failed:
                    fh.write(f"{spec.key}\t{spec.summary}\t{reason}\n")
            print(f"\nFailed list written to {args.failed_output}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
