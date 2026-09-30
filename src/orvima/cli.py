"""orvima command line.

    orvima demo                   pointers for the offline tour
    orvima serve --mode real      run the local API at http://127.0.0.1:8301
    orvima mcp                    stdio MCP server for any AI tool
    orvima run "your goal"        headless agent loop
    orvima --version
"""

from __future__ import annotations

import json
import os
import sys

from . import __version__


def _out(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_demo() -> int:
    print(
        "orvima demo: offline tour — no Chrome, no internet, no keys.\n"
        "  orvima run \"send a message to Acme support\"\n"
        "  orvima mcp           (demo browser; add to any MCP client)\n"
        "  orvima serve --mode demo\n"
        "\nReal mode (a live Chromium you watch):\n"
        "  orvima serve --mode real\n"
        "  orvima run \"summarize the top story on hackernews\" --mode real"
    )
    return 0


def cmd_serve(host: str, port: int, mode: str) -> int:
    import uvicorn  # noqa: PLC0415

    from .api import app  # noqa: PLC0415 - lazy so --version stays light

    # mode is per-session when creating a session; server just carries the app
    _mode_env(mode)
    print(f"orvima API listening on http://{host}:{port}  (docs at /docs)")
    print("new session -> POST /api/sessions  |  watch -> GET /api/sessions/{id}/events")
    if mode == "demo":
        print("demo mode: every session runs against the offline acme.dev simulator")
    else:
        print("real mode: sessions launch a local Chromium (playwright)")
    return uvicorn.run(app, host=host, port=port, log_level="warning")


def cmd_mcp(mode: str) -> int:
    from .mcp_server import run  # noqa: PLC0415

    return run(demo=(mode == "demo"), name="orvima")


def cmd_run(goal: str, mode: str, max_steps: int) -> int:
    from .agent import AgentLoop, SessionStore  # noqa: PLC0415

    store = SessionStore()
    sess = store.create(mode=mode)
    try:
        result = AgentLoop(sess, max_steps=max_steps).run(goal)
        if not result.get("ok"):
            _out(result)
            return 1
        _out(result)
        print("\ntranscript:")
        for row in sess.transcript:
            kind = row["kind"]
            if kind == "tool_call":
                print(f"  step {row['step']}: {row['tool']}({_brief(row['args'])})")
            elif kind == "tool_result":
                ok = row["result"].get("ok")
                print(f"      -> ok={ok} {_brief(row['result'])[:160]}")
            elif kind == "goal":
                print(f"  goal: {row['goal']}")
        return 0
    finally:
        sess.close()


def _brief(data: dict) -> str:
    return str({k: v for k, v in data.items() if k not in ("png_b64",)})


def _mode_env(mode: str) -> None:
    os.environ.setdefault("ORVIMA_MODE", mode)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="orvima",
        description="The browser your AI drives — and you can watch. Local-first, MCP-native, no cloud.",
    )
    parser.add_argument("--version", action="version", version=f"orvima {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("demo", help="offline tour — try everything with zero setup")

    p_serve = sub.add_parser("serve", help="run the local API + UI (http://127.0.0.1:8301)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8301)
    p_serve.add_argument("--mode", default=None, choices=["demo", "real"])

    p_mcp = sub.add_parser("mcp", help="stdio MCP server for any AI tool")
    p_mcp.add_argument("--mode", default=None, choices=["demo", "real"])

    p_run = sub.add_parser("run", help="run a goal as a headless agent loop")
    p_run.add_argument("goal")
    p_run.add_argument("--mode", default=None, choices=["demo", "real"])
    p_run.add_argument("--max-steps", type=int, default=20, help="cap on actions before giving up")

    for p in (p_serve, p_mcp, p_run):
        p.add_argument("--browser", default=None, choices=["chrome", "msedge", "chromium"],
                       help="default: autodetect your installed Chrome/Edge")
        p.add_argument("--attach", default=None, metavar="CDP_URL",
                       help="drive an already-running browser, e.g. http://127.0.0.1:9222")
        p.add_argument("--headless", action="store_true", help="no visible window (CI/pod-friendly)")

    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    mode = getattr(args, "mode", None) or os.environ.get("ORVIMA_MODE", "demo")
    if getattr(args, "browser", None):
        os.environ["ORVIMA_BROWSER"] = args.browser
    if getattr(args, "attach", None):
        os.environ["ORVIMA_ATTACH"] = args.attach
    if getattr(args, "headless", False):
        os.environ["ORVIMA_HEADLESS"] = "1"

    try:
        if not args.command:
            parser.print_help()
            return 0
        if args.command == "demo":
            return cmd_demo()
        if args.command == "serve":
            return cmd_serve(args.host, args.port, mode)
        if args.command == "mcp":
            return cmd_mcp(mode)
        if args.command == "run":
            return cmd_run(args.goal, mode, args.max_steps)
        return 2
    except Exception as exc:  # noqa: BLE001 - friendly CLI errors
        print(f"orvima: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
