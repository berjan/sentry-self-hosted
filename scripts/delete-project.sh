#!/bin/bash
# Delete a Sentry project
# Usage: ./delete-project.sh <project-slug>
#
# WARNING: This permanently deletes the project and all its data!

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

if [ -z "$1" ]; then
    echo "Usage: $0 <project-slug>"
    echo ""
    echo "WARNING: This permanently deletes the project and all its data!"
    exit 1
fi

SLUG="$1"

echo "WARNING: This will permanently delete project '$SLUG' and all its data!"
read -p "Are you sure? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Deleting project: $SLUG"

docker compose exec -T web sentry shell << EOF
from sentry.models.project import Project

try:
    proj = Project.objects.get(slug='$SLUG')
    name = proj.name
    proj.delete()
    print(f"Deleted project: {name} ($SLUG)")
except Project.DoesNotExist:
    print(f"Project '$SLUG' not found")
EOF
