# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""Sentry CLI — query issues, events and traces from a self-hosted Sentry instance.

Usage:
    uv run /srv/sentry/scripts/sentry-cli.py <command> [options]

Configuration:
    Set SENTRY_TOKEN env var or create /srv/sentry/.env.sentry-cli with:
        SENTRY_TOKEN=<your-token>

    Run `sentry-cli.py setup` for token creation instructions.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_URL = "http://192.168.1.75:9500"
DEFAULT_ORG = "sentry"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env.sentry-cli"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_token_from_env_file() -> str | None:
    """Read SENTRY_TOKEN from the .env.sentry-cli file."""
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "SENTRY_TOKEN":
            return value.strip().strip("\"'")
    return None


def get_token(args: argparse.Namespace) -> str:
    token = args.token or os.environ.get("SENTRY_TOKEN") or load_token_from_env_file()
    if not token:
        print(
            "Error: No API token found.\n"
            "Set SENTRY_TOKEN env var, pass --token, or create "
            f"{ENV_FILE}\n"
            "Run `sentry-cli.py setup` for instructions.",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def relative_time(iso: str | None) -> str:
    """Convert an ISO timestamp to a human-friendly relative string."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return iso
    delta = datetime.now(timezone.utc) - dt
    secs = int(delta.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 60:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    return f"{months}mo ago"


def truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def print_table(rows: list[dict], columns: list[tuple[str, str, int]]) -> None:
    """Print *rows* as an aligned table.

    *columns* is a list of (header, key, max_width) tuples.
    """
    if not rows:
        print("No results.")
        return

    # Build string matrix
    header = []
    widths: list[int] = []
    for title, _, max_w in columns:
        header.append(title)
        widths.append(len(title))

    str_rows: list[list[str]] = []
    for row in rows:
        cells: list[str] = []
        for i, (_, key, max_w) in enumerate(columns):
            val = str(row.get(key, ""))
            val = truncate(val, max_w)
            cells.append(val)
            widths[i] = max(widths[i], len(val))
        str_rows.append(cells)

    # Clamp widths
    for i, (_, _, max_w) in enumerate(columns):
        widths[i] = min(widths[i], max_w)

    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*header))
    print(fmt.format(*("─" * w for w in widths)))
    for cells in str_rows:
        print(fmt.format(*cells))


class SentryClient:
    def __init__(self, base_url: str, token: str, org: str):
        self.base_url = base_url.rstrip("/")
        self.org = org
        self.http = httpx.Client(
            base_url=f"{self.base_url}/api/0",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

    # -- projects ----------------------------------------------------------
    def list_projects(self) -> list[dict]:
        r = self.http.get(f"/organizations/{self.org}/projects/")
        r.raise_for_status()
        return r.json()

    # -- issues ------------------------------------------------------------
    def list_issues(self, project: str, query: str = "is:unresolved") -> list[dict]:
        r = self.http.get(
            f"/projects/{self.org}/{project}/issues/",
            params={"query": query},
        )
        r.raise_for_status()
        return r.json()

    def get_issue(self, issue_id: str) -> dict:
        r = self.http.get(f"/issues/{issue_id}/")
        r.raise_for_status()
        return r.json()

    def resolve_issue(self, issue_id: str) -> dict:
        r = self.http.put(
            f"/issues/{issue_id}/",
            json={"status": "resolved"},
        )
        r.raise_for_status()
        return r.json()

    # -- events ------------------------------------------------------------
    def list_events(self, issue_id: str) -> list[dict]:
        r = self.http.get(f"/issues/{issue_id}/events/")
        r.raise_for_status()
        return r.json()

    def get_event(self, issue_id: str, event_id: str) -> dict:
        r = self.http.get(f"/issues/{issue_id}/events/{event_id}/")
        r.raise_for_status()
        return r.json()

    def get_latest_event(self, issue_id: str) -> dict:
        r = self.http.get(f"/issues/{issue_id}/events/latest/")
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_stacktrace(entries: list[dict]) -> str:
    """Render exception entries into a readable stacktrace."""
    parts: list[str] = []
    for entry in entries:
        if entry.get("type") != "exception":
            continue
        for exc in entry.get("data", {}).get("values", []):
            exc_type = exc.get("type", "Exception")
            exc_value = exc.get("value", "")
            parts.append(f"{exc_type}: {exc_value}")
            frames = exc.get("stacktrace", {}).get("frames", [])
            for frame in frames:
                filename = frame.get("filename", "?")
                lineno = frame.get("lineNo") or frame.get("lineno") or "?"
                func = frame.get("function", "?")
                parts.append(f"  {filename}:{lineno} in {func}")
                ctx_line = frame.get("contextLine") or frame.get("context_line")
                if ctx_line:
                    parts.append(f"    > {ctx_line.strip()}")
            parts.append("")
    return "\n".join(parts)


def print_event_detail(event: dict) -> None:
    """Pretty-print a single event."""
    print(f"Event:     {event.get('eventID', '?')}")
    print(f"Title:     {event.get('title', '?')}")
    print(f"Date:      {event.get('dateCreated', '?')}  ({relative_time(event.get('dateCreated'))})")
    print(f"Platform:  {event.get('platform', '?')}")

    tags = event.get("tags", [])
    if tags:
        print(f"Tags:      ", end="")
        tag_strs = [f"{t.get('key')}={t.get('value')}" for t in tags]
        print(", ".join(tag_strs))

    ctx = event.get("context", {}) or event.get("contexts", {})
    if ctx:
        browser = ctx.get("browser", {})
        os_ctx = ctx.get("os", {})
        if browser:
            print(f"Browser:   {browser.get('name', '?')} {browser.get('version', '')}")
        if os_ctx:
            print(f"OS:        {os_ctx.get('name', '?')} {os_ctx.get('version', '')}")

    entries = event.get("entries", [])
    trace = format_stacktrace(entries)
    if trace:
        print("\n--- Stacktrace ---")
        print(trace)

    # Message / breadcrumbs summary
    for entry in entries:
        if entry.get("type") == "message":
            print(f"\nMessage: {entry.get('data', {}).get('formatted', '')}")
        if entry.get("type") == "breadcrumbs":
            crumbs = entry.get("data", {}).get("values", [])
            if crumbs:
                print(f"\nBreadcrumbs ({len(crumbs)}):")
                for c in crumbs[-10:]:
                    cat = c.get("category", "")
                    msg = c.get("message", "")
                    ts = relative_time(c.get("timestamp"))
                    print(f"  [{cat}] {truncate(msg, 80)}  ({ts})")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_setup(_args: argparse.Namespace) -> None:
    url = _args.url
    print(textwrap.dedent(f"""\
        Sentry CLI — one-time setup
        ═══════════════════════════

        1. Open the Sentry token page:
           {url}/settings/account/api/auth-tokens/

        2. Create a new token with these scopes:
           • project:read
           • event:read
           • event:write
           • org:read

        3. Save the token to {ENV_FILE}:
           echo 'SENTRY_TOKEN=<paste-token>' > {ENV_FILE}

        Or export it in your shell:
           export SENTRY_TOKEN=<paste-token>
    """))


def cmd_projects(args: argparse.Namespace) -> None:
    client = SentryClient(args.url, get_token(args), args.org)
    projects = client.list_projects()
    if args.json:
        print(json.dumps(projects, indent=2))
        return
    print_table(
        projects,
        [
            ("ID", "id", 8),
            ("Slug", "slug", 30),
            ("Name", "name", 40),
            ("Platform", "platform", 15),
        ],
    )


def cmd_issues_list(args: argparse.Namespace) -> None:
    client = SentryClient(args.url, get_token(args), args.org)
    query = args.query or "is:unresolved"
    issues = client.list_issues(args.project, query)
    if args.json:
        print(json.dumps(issues, indent=2))
        return
    rows = []
    for i in issues:
        rows.append({
            "id": str(i.get("id", "")),
            "title": i.get("title", ""),
            "culprit": i.get("culprit", ""),
            "events": str(i.get("count", "")),
            "users": str(i.get("userCount", "")),
            "last_seen": relative_time(i.get("lastSeen")),
        })
    print_table(
        rows,
        [
            ("ID", "id", 10),
            ("Title", "title", 55),
            ("Culprit", "culprit", 35),
            ("Events", "events", 7),
            ("Users", "users", 6),
            ("Last Seen", "last_seen", 12),
        ],
    )


def cmd_issues_show(args: argparse.Namespace) -> None:
    client = SentryClient(args.url, get_token(args), args.org)
    issue = client.get_issue(args.issue_id)
    if args.json:
        print(json.dumps(issue, indent=2))
        return
    print(f"Issue:      #{issue.get('id', '?')}")
    print(f"Title:      {issue.get('title', '?')}")
    print(f"Culprit:    {issue.get('culprit', '?')}")
    print(f"Status:     {issue.get('status', '?')}")
    print(f"Level:      {issue.get('level', '?')}")
    print(f"Platform:   {issue.get('platform', '?')}")
    print(f"Project:    {issue.get('project', {}).get('slug', '?')}")
    print(f"Events:     {issue.get('count', '?')}")
    print(f"Users:      {issue.get('userCount', '?')}")
    print(f"First Seen: {issue.get('firstSeen', '?')}  ({relative_time(issue.get('firstSeen'))})")
    print(f"Last Seen:  {issue.get('lastSeen', '?')}  ({relative_time(issue.get('lastSeen'))})")
    link = issue.get("permalink") or f"{args.url}/organizations/{args.org}/issues/{issue.get('id')}/"
    print(f"Link:       {link}")


def cmd_issues_resolve(args: argparse.Namespace) -> None:
    client = SentryClient(args.url, get_token(args), args.org)
    issue = client.resolve_issue(args.issue_id)
    if args.json:
        print(json.dumps(issue, indent=2))
        return
    print(f"Resolved issue #{issue.get('id', args.issue_id)}: {issue.get('title', '')}")


def cmd_events_list(args: argparse.Namespace) -> None:
    client = SentryClient(args.url, get_token(args), args.org)
    events = client.list_events(args.issue_id)
    if args.json:
        print(json.dumps(events, indent=2))
        return
    rows = []
    for e in events:
        rows.append({
            "id": e.get("eventID", e.get("id", ""))[:12],
            "title": e.get("title", ""),
            "date": relative_time(e.get("dateCreated")),
        })
    print_table(
        rows,
        [
            ("Event ID", "id", 14),
            ("Title", "title", 60),
            ("Date", "date", 12),
        ],
    )


def cmd_events_show(args: argparse.Namespace) -> None:
    client = SentryClient(args.url, get_token(args), args.org)
    event = client.get_event(args.issue_id, args.event_id)
    if args.json:
        print(json.dumps(event, indent=2))
        return
    print_event_detail(event)


def cmd_events_latest(args: argparse.Namespace) -> None:
    client = SentryClient(args.url, get_token(args), args.org)
    event = client.get_latest_event(args.issue_id)
    if args.json:
        print(json.dumps(event, indent=2))
        return
    print_event_detail(event)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sentry-cli.py",
        description="Query issues, events and traces from Sentry.",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--url", default=DEFAULT_URL, help="Sentry base URL")
    parser.add_argument("--token", default=None, help="API token (overrides env/file)")
    parser.add_argument("--org", default=DEFAULT_ORG, help="Organization slug")

    sub = parser.add_subparsers(dest="command")

    # setup
    sub.add_parser("setup", help="Print token creation instructions")

    # projects
    sub.add_parser("projects", help="List all projects")

    # issues
    issues_parser = sub.add_parser("issues", help="Manage issues")
    issues_sub = issues_parser.add_subparsers(dest="issues_command")

    issues_list = issues_sub.add_parser("list", help="List issues for a project")
    issues_list.add_argument("-p", "--project", required=True, help="Project slug")
    issues_list.add_argument("-q", "--query", default=None, help="Search query (default: is:unresolved)")

    issues_show = issues_sub.add_parser("show", help="Show issue details")
    issues_show.add_argument("issue_id", help="Issue ID")

    issues_resolve = issues_sub.add_parser("resolve", help="Resolve an issue")
    issues_resolve.add_argument("issue_id", help="Issue ID")

    # events
    events_parser = sub.add_parser("events", help="View events")
    events_sub = events_parser.add_subparsers(dest="events_command")

    events_list = events_sub.add_parser("list", help="List events for an issue")
    events_list.add_argument("issue_id", help="Issue ID")

    events_show = events_sub.add_parser("show", help="Show full event detail")
    events_show.add_argument("issue_id", help="Issue ID")
    events_show.add_argument("event_id", help="Event ID")

    events_latest = events_sub.add_parser("latest", help="Show latest event for an issue")
    events_latest.add_argument("issue_id", help="Issue ID")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "setup": cmd_setup,
        "projects": cmd_projects,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
        return

    if args.command == "issues":
        if not args.issues_command:
            print("Usage: sentry-cli.py issues {list,show,resolve}", file=sys.stderr)
            sys.exit(1)
        {"list": cmd_issues_list, "show": cmd_issues_show, "resolve": cmd_issues_resolve}[
            args.issues_command
        ](args)
        return

    if args.command == "events":
        if not args.events_command:
            print("Usage: sentry-cli.py events {list,show,latest}", file=sys.stderr)
            sys.exit(1)
        {"list": cmd_events_list, "show": cmd_events_show, "latest": cmd_events_latest}[
            args.events_command
        ](args)
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
