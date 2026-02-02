#!/bin/bash
# List all Sentry projects and their DSNs
# Usage: ./list-projects.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "Sentry Projects"
echo "==============="
echo ""

docker compose exec -T web sentry shell << 'EOF'
from sentry.models.project import Project
from sentry.models.projectkey import ProjectKey

projects = Project.objects.all().order_by('id')

if not projects:
    print("No projects found.")
else:
    for proj in projects:
        key = ProjectKey.objects.filter(project=proj).first()
        dsn = key.dsn_public if key else "No key"
        print(f"[{proj.id}] {proj.name} ({proj.slug})")
        print(f"    DSN: {dsn}")
        print("")
EOF
