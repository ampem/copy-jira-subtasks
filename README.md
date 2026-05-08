# copy-jira-subtasks

A CLI tool that copies subtasks from one Jira issue to another. Useful for duplicating sprint templates, replicating checklists, or cloning subtask structures across issues.

## Requirements

- Docker and Docker Compose
- A Jira Personal Access Token (PAT)

## Usage

```
python copy_subtasks.py \
  --url https://jira.example.com \
  --token <PAT> \
  --source PROJ-123 \
  --target PROJ-456
```

Credentials can also be supplied via environment variables:

| Variable     | Description              |
|--------------|--------------------------|
| `JIRA_URL`   | Jira base URL            |
| `JIRA_TOKEN` | Personal Access Token    |

### Options

| Flag                    | Description                                                    |
|-------------------------|----------------------------------------------------------------|
| `--source ISSUE_KEY`    | Source issue to copy subtasks from (required)                  |
| `--target ISSUE_KEY`    | Target issue to create subtasks under (required)               |
| `--filter-include REGEX`| Only copy subtasks whose summary matches this regex            |
| `--filter-exclude REGEX`| Skip subtasks whose summary matches this regex                 |
| `--copy-description`    | Also copy the description field from each subtask              |
| `--copy-assignee`       | Also copy the assignee field from each subtask                 |
| `--subtask-type NAME`   | Jira issue type name for created subtasks (default: `Sub-task`)|
| `--yes`, `-y`           | Skip the confirmation prompt                                   |
| `--failed-output FILE`  | Write failed subtask keys/summaries to a TSV file              |

### Examples

```bash
# Copy all subtasks, auto-confirm
python copy_subtasks.py --source PROJ-1 --target PROJ-2 --yes

# Copy only subtasks whose summary starts with "Backend"
python copy_subtasks.py --source PROJ-1 --target PROJ-2 \
  --filter-include "^Backend" --yes

# Copy everything except Frontend subtasks, including descriptions and assignees
python copy_subtasks.py --source PROJ-1 --target PROJ-2 \
  --filter-exclude "^Frontend" \
  --copy-description --copy-assignee --yes

# Capture any failures to a file
python copy_subtasks.py --source PROJ-1 --target PROJ-2 \
  --yes --failed-output failed.tsv
```

## Jira PAT Scopes

When creating a Personal Access Token in Jira (Server/Data Center), no granular OAuth scopes are selected — the token inherits your user account's permissions. The Jira **user account** must have:

| Permission                 | Why it is needed                                                |
|----------------------------|-----------------------------------------------------------------|
| **Browse Projects**        | Read the source issue and its subtasks (`GET /rest/api/2/issue/{key}`) |
| **Create Issues**          | Create new subtasks under the target issue (`POST /rest/api/2/issue`) |
| **Assign Issues** *(optional)* | Required only when using `--copy-assignee` and assigning to other users |

> **Jira Cloud note:** If using Jira Cloud with an API token (Basic Auth), the token owner must have the same project-level permissions listed above. Cloud does not use the PAT Bearer header — use Basic Auth with your email and API token instead.

## Running Tests

Tests run entirely inside Docker Compose against a mock Jira server:

```bash
docker compose run --rm test
```

This starts the mock Jira service, runs all test scenarios defined in `tests/run_tests.sh`, and prints a pass/fail summary.

## Docker

Run the tool via Docker without installing Python locally:

```bash
docker compose build app
docker compose run --rm app \
  --url https://jira.example.com \
  --token "$JIRA_TOKEN" \
  --source PROJ-123 \
  --target PROJ-456
```
