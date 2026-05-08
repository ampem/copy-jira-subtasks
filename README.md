# copy-jira-subtasks

A CLI tool that copies subtasks from one Jira issue to another. Useful for duplicating sprint templates, replicating checklists, or cloning subtask structures across issues.

## Requirements

- Docker and Docker Compose
- A Jira API token
- For Jira Cloud: your Atlassian account email

## Usage

**Jira Server / Data Center** (Bearer token):
```
python copy_subtasks.py \
  --url https://jira.example.com \
  --token <API_TOKEN> \
  --source PROJ-123 \
  --target PROJ-456
```

**Jira Cloud** (Basic Auth):
```
python copy_subtasks.py \
  --url https://your-domain.atlassian.net \
  --email your@email.com \
  --token <API_TOKEN> \
  --source PROJ-123 \
  --target PROJ-456
```

Credentials can also be supplied via environment variables:

| Variable         | Description                                        |
|------------------|----------------------------------------------------|
| `JIRA_URL`       | Jira base URL                                      |
| `JIRA_API_TOKEN` | API token                                          |
| `JIRA_EMAIL`     | Atlassian account email (Jira Cloud only)          |

### Options

| Flag                    | Description                                                    |
|-------------------------|----------------------------------------------------------------|
| `--email EMAIL`         | Atlassian account email for Jira Cloud Basic Auth              |
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

### Jira Server / Data Center (PAT — Bearer token)

PATs on Jira Server/Data Center inherit your user account's project permissions; there are no granular OAuth scopes to select. The account must have the following **project-level permissions** on both the source and target projects:

| Project permission             | Why it is needed                                                        |
|--------------------------------|-------------------------------------------------------------------------|
| **Browse Projects**            | Read the source issue and its subtask list (`GET /rest/api/2/issue/{key}`) |
| **Create Issues**              | Create new subtasks under the target issue (`POST /rest/api/2/issue`)  |
| **Assign Issues** *(optional)* | Required only when using `--copy-assignee` and assigning to other users |

### Jira Cloud (API token — Basic Auth)

Jira Cloud does not accept PAT Bearer tokens. Use Basic Auth with your Atlassian account email and an API token generated at `id.atlassian.com`. When authorising an OAuth 2.0 app, request the following granular scopes:

| Scope                   | Required | Why it is needed                                         |
|-------------------------|----------|----------------------------------------------------------|
| `read:issue:jira`       | Yes      | Read the source issue, its subtask list, descriptions, and priorities |
| `read:project:jira`     | Yes      | Resolve the project key from the target issue            |
| `write:issue:jira`      | Yes      | Create new subtasks (`POST /rest/api/2/issue`)           |
| `read:user:jira`        | Optional | Read assignee display names when using `--copy-assignee` |

> The classic equivalents are `read:jira-work`, `write:jira-work`, and (for assignees) `read:jira-user`, if your app does not support granular scopes.

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
docker compose run --rm \
  -e JIRA_URL=https://your-domain.atlassian.net \
  -e JIRA_EMAIL="$JIRA_EMAIL" \
  -e JIRA_API_TOKEN="$JIRA_API_TOKEN" \
  app \
  --source PROJ-123 \
  --target PROJ-456
```
