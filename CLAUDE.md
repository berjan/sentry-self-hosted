# Sentry Self-Hosted

Error tracking for Django applications.

## Access

- **URL:** http://localhost:9500
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

## Integrated Projects

| Project | DSN Location |
|---------|--------------|
| SlimFactuur | `/srv/slimfactuur/.env` |
| InstallatieAssistent | `/srv/bruensdt/.env` |
