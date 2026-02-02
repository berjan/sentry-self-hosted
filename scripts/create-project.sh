#!/bin/bash
# Create a new Sentry project and output its DSN
# Usage: ./create-project.sh <project-slug> [project-name]
#
# Examples:
#   ./create-project.sh slimfactuur "SlimFactuur"
#   ./create-project.sh trading

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

if [ -z "$1" ]; then
    echo "Usage: $0 <project-slug> [project-name]"
    echo ""
    echo "Examples:"
    echo "  $0 slimfactuur 'SlimFactuur'"
    echo "  $0 trading 'Trading Platform'"
    exit 1
fi

SLUG="$1"
NAME="${2:-$1}"

echo "Creating Sentry project: $NAME (slug: $SLUG)"
echo ""

docker compose exec -T web sentry shell << EOF
from sentry.models.project import Project
from sentry.models.organization import Organization
from sentry.models.projectkey import ProjectKey

org = Organization.objects.get(slug='sentry')

# Create or get project
try:
    proj = Project.objects.get(slug='$SLUG')
    print(f"Project '$SLUG' already exists (id={proj.id})")
except Project.DoesNotExist:
    proj = Project.objects.create(
        name='$NAME',
        slug='$SLUG',
        organization=org
    )
    print(f"Created project: $NAME (id={proj.id})")

# Get or create DSN key
key = ProjectKey.objects.filter(project=proj).first()
if not key:
    key = ProjectKey.objects.create(project=proj, label='Default')
    print("Created new project key")

dsn = key.dsn_public
print("")
print("=" * 60)
print(f"Project: {proj.name}")
print(f"Slug: {proj.slug}")
print(f"DSN: {dsn}")
print("=" * 60)
print("")
print("Add to your .env file:")
print(f"SENTRY_DSN={dsn}")
EOF
