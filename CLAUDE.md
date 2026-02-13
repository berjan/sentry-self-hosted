# Sentry Self-Hosted

Error tracking for Django applications.

## Access

- **External URL:** https://sentry.dev.bruens.it
- **Internal URL:** http://192.168.1.75:9500
- **Admin:** berjan@bruens.it

## Project Management Scripts

```bash
# List all projects and DSNs
./scripts/list-projects.sh

# Create new project
./scripts/create-project.sh <slug> [name]
# Example: ./scripts/create-project.sh trading "Trading Platform"

# Delete project (with confirmation)
./scripts/delete-project.sh <slug>
```

## Sentry CLI (API)

Query issues, events and traces via the Sentry API. Requires a one-time token setup — run `setup` for instructions.

```bash
# Setup instructions
uv run /srv/sentry/scripts/sentry-cli.py setup

# List projects
uv run /srv/sentry/scripts/sentry-cli.py projects

# List unresolved issues for a project
uv run /srv/sentry/scripts/sentry-cli.py issues list -p slimfactuur

# Show issue details
uv run /srv/sentry/scripts/sentry-cli.py issues show <id>

# Resolve an issue
uv run /srv/sentry/scripts/sentry-cli.py issues resolve <id>

# View latest event with stacktrace
uv run /srv/sentry/scripts/sentry-cli.py events latest <issue_id>

# JSON output for scripting
uv run /srv/sentry/scripts/sentry-cli.py --json issues list -p slimfactuur | jq '.[].title'
```

Token is stored in `/srv/sentry/.env.sentry-cli` (gitignored).

## Integrated Projects

| Project | DSN Location |
|---------|--------------|
| SlimFactuur | `/srv/slimfactuur/.env` |
| InstallatieAssistent | `/srv/bruensdt/.env` |
