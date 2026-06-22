#!/usr/bin/env python3
"""Pre-flight health check for the AlignAI stack.

Verifies every service the app depends on is up and reachable before you start
working on route handlers, the agent graph, or the frontend. Run it after
`docker-compose up` (and once your Qdrant Cloud creds are in the root .env):

    python healthcheck.py

Exit code 0 = everything healthy, 1 = at least one service is down.
Stdlib only — no venv or pip install required.
"""

from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
from functools import partial
from pathlib import Path

TIMEOUT = 5  # seconds per check
ENV_FILE = Path(__file__).parent / ".env"

if sys.stdout.isatty():
    GREEN, RED, YELLOW, RESET = "\033[0;32m", "\033[0;31m", "\033[1;33m", "\033[0m"
else:  # piped or redirected (CI logs, files) — skip ANSI codes
    GREEN = RED = YELLOW = RESET = ""


def load_env(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines from a .env file, ignoring comments and blanks."""
    if not path.exists():
        return {}
    pairs = (
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )
    return {k.strip(): v.strip().strip("\"'") for k, v in pairs}


def probe_tcp(host: str, port: int) -> str | None:
    """Return None if the port accepts connections, else an error message.

    Note: this only confirms the port is open, not that the service behind it
    is ready to serve (e.g. Postgres accepting queries). Good enough as a
    liveness pre-check without pulling in a DB client.
    """
    try:
        socket.create_connection((host, port), timeout=TIMEOUT).close()
        return None
    except OSError as exc:
        return f"cannot connect to {host}:{port} ({exc})"


def probe_http(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_status: str = "",
    label: str = "",
) -> str | None:
    """Return None if the URL returns 200 (and matches json_status), else an error.

    `label` replaces the URL in error messages so secrets in the URL (e.g. a
    Qdrant Cloud endpoint) never reach stdout. Defaults to the URL itself.
    """
    where = label or url
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers or {}), timeout=TIMEOUT
        ) as resp:
            body = resp.read(2048)
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code} from {where}"
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return f"cannot reach {where} ({reason})"

    if json_status:
        try:
            if json.loads(body).get("status") != json_status:
                return f'{where}: expected status "{json_status}"'
        except json.JSONDecodeError:
            return f"{where}: response is not JSON"
    return None


def check_qdrant(env: dict[str, str]) -> str | None:
    url = env.get("QDRANT_URL", "").rstrip("/")
    if not url:
        return "QDRANT_URL not set in root .env (Qdrant Cloud URL required)"
    headers = {"api-key": key} if (key := env.get("QDRANT_API_KEY")) else {}
    return probe_http(f"{url}/healthz", headers=headers, label="Qdrant Cloud endpoint")


def main() -> int:
    env = load_env(ENV_FILE)
    checks = {
        "PostgreSQL (container)": partial(probe_tcp, "localhost", 5432),
        "Qdrant Cloud": partial(check_qdrant, env),
        "Backend (FastAPI)": partial(probe_http, "http://localhost:8000/health", json_status="ok"),
        "Agent (LangGraph)": partial(probe_http, "http://localhost:8123/ok"),
        "Frontend (Nginx)": partial(probe_http, "http://localhost/"),
    }

    print("🔍 AlignAI service health check")
    print("=" * 40)

    failures = 0
    for name, check in checks.items():
        error = check()
        status = f"{GREEN}✓ UP{RESET}" if error is None else f"{RED}✗ DOWN{RESET}"
        print(f"  {name:<24} {status}  {error or ''}")
        failures += error is not None

    print("=" * 40)
    if not failures:
        print(f"{GREEN}✅ All services healthy.{RESET}")
        return 0
    print(
        f"{RED}❌ {failures} service(s) down.{RESET} "
        f"{YELLOW}Check: docker-compose ps / docker-compose logs -f{RESET}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
