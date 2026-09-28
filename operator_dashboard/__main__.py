from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="operator_dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8866)
    args = parser.parse_args(argv)
    token = os.environ.get("DASHBOARD_AUTH_TOKEN")
    if not token:
        sys.stderr.write("DASHBOARD_AUTH_TOKEN is required.\n")
        return 2
    if args.host in {"0.0.0.0", "::", "[::]"} and not token:
        sys.stderr.write("Public bind requires DASHBOARD_AUTH_TOKEN.\n")
        return 2
    import uvicorn

    uvicorn.run(
        "operator_dashboard.api:create_app",
        host=args.host,
        port=int(args.port),
        factory=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
