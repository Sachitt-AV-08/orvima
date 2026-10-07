"""orvima command line.

    orvima demo                   pointers for the offline tour
    orvima serve --mode real      run the local API at http://127.0.0.1:8301
    orvima mcp                    stdio MCP server for any AI tool
    orvima run "your goal"        headless agent loop
    orvima doctor                 health check: browser, profile, port, LLM, MCP
    orvima --version
"""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.request

from . import __version__
from .browser import DEFAULT_PROFILE, bundled_chromium_path, detect_channel


def _out(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_demo() -> int:
    print(
        "orvima demo: offline tour - no Chrome, no internet, no keys.\n"
        "This is the simulated site, and it is opt-in. orvima runs against a real\n"
        "browser by default, so nothing here is a preview of what your AI sees.\n"
        "\nTo try it:\n"
        "  orvima run \"send a message to Acme support\" --mode demo\n"
        "  orvima mcp --mode demo        (add to any MCP client)\n"
        "  orvima serve --mode demo\n"
        "\nReal mode (the default - a live Chromium you watch):\n"
        "  orvima serve\n"
        "  orvima run \"summarize the top story on hackernews\""
    )
    return 0


def is_loopback(host: str) -> bool:
    """Whether binding `host` keeps the port on this machine only.

    Resolved rather than string-matched, because the strings that matter are not
    all loopback: an empty host means every interface, and a hostname like
    `127.0.0.1.example.com` merely contains a loopback address.
    """
    import ipaddress
    import socket as _socket

    candidate = (host or "").strip()
    if not candidate:
        return False  # 0.0.0.0 / all interfaces
    bare = candidate.strip("[]")
    try:
        return ipaddress.ip_address(bare).is_loopback
    except ValueError:
        pass
    try:
        resolved = _socket.getaddrinfo(candidate, None, proto=_socket.IPPROTO_TCP)
    except OSError:
        return False  # unresolvable: cannot be shown to be local
    for info in resolved:
        address = info[4][0]
        try:
            if not ipaddress.ip_address(address).is_loopback:
                return False
        except ValueError:
            return False
    return bool(resolved)


def check_bind(host: str) -> str | None:
    """Why this bind is unsafe, or None if it is fine.

    The refusal is at startup rather than per request because the alternative -
    an endpoint that rejects unauthenticated calls - still means the port is
    open and serving a logged-in browser's control surface to the network. The
    refusal has to be "orvima will not start like that".

    Loopback needs no token: there is no trust boundary to cross. Everything
    else does, because `--host` exists and someone will eventually use it to
    reach orvima from a phone.
    """
    if is_loopback(host):
        return None
    from .api import configured_token  # noqa: PLC0415 - keeps --version light

    if configured_token():
        return None
    return (
        f"refusing to serve on {host or '(every interface)'}: that puts an "
        "unauthenticated approval endpoint - which can spend money in a real "
        "logged-in browser - on your network.\n"
        "  Fix one of:\n"
        "    set ORVIMA_API_TOKEN to a secret you generate, and send it as\n"
        f"      the X-Orvima-Token header or 'Authorization: Bearer <token>'\n"
        "    or bind loopback instead: --host 127.0.0.1\n"
        "  Reaching it from a phone is better done over Tailscale than by "
        "exposing this port to a network."
    )


def cmd_serve(host: str, port: int, mode: str) -> int:
    import uvicorn  # noqa: PLC0415

    problem = check_bind(host)
    if problem:
        print(f"orvima: {problem}", file=sys.stderr)
        return 1

    # mode is per-session when creating a session; server just carries the app
    _mode_env(mode)
    # create_app re-checks the bind, so the guard holds for any caller and not
    # just this one.
    from .api import create_app  # noqa: PLC0415 - lazy so --version stays light

    app = create_app(host)
    print(f"orvima API listening on http://{host}:{port}  (docs at /docs)")
    print("new session -> POST /api/sessions  |  watch -> GET /api/sessions/{id}/events")
    if mode == "demo":
        print("demo mode: every session runs against the offline acme.dev simulator")
    else:
        print("real mode: sessions launch a local Chromium (playwright)")
    from .api import configured_token  # noqa: PLC0415

    if configured_token():
        print(
            "API token set: acting endpoints require it. Keep it off shared "
            "screens and out of shell history."
        )
    else:
        print(
            f"no API token set, so acting endpoints are open to anything on "
            f"{host} - fine on loopback, not fine on a network"
        )
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


def resolve_mode(mode: str | None) -> str:
    """Which mode this invocation will actually run in.

    One function, so `doctor` cannot disagree with the commands it checks.

    The default is `real`. It used to be `demo`, and that default was the whole
    problem: `orvima mcp` with no flags served a scripted acme.dev and answered
    `{"ok": true}` about it, so a client could be told it had read a website no
    browser ever opened. The offline tour is still there and still one command
    away -- `orvima demo`, or `--mode demo` -- but it is now something you ask
    for rather than something you inherit.
    """
    return mode or os.environ.get("ORVIMA_MODE", "real")


def _warn_inert_browser_flag(browser: str | None, mode: str) -> None:
    """Say so when `--browser` will have no effect.

    In demo mode there is no browser behind orvima, so the channel is stored
    and never read. A flag that is accepted and does nothing reads as "that part
    is configured", which is how a config asking for Brave came to be serving
    acme.dev for an entire session without a word of complaint.
    """
    if browser and mode != "real":
        print(
            f"orvima: --browser {browser} has no effect in {mode} mode — there is "
            "no real browser behind this. Add --mode real (or set ORVIMA_MODE=real) "
            "to drive an actual browser.",
            file=sys.stderr,
        )


def cmd_doctor(mode: str | None = None) -> int:
    """Run a health check on the Orvima environment.

    Reports the mode it would run in, and fails when that mode is not the one
    that drives a browser. A health check that passes while the product is in a
    non-functional configuration is worse than none: it is trusted.
    """
    from pathlib import Path

    checks = []
    active = resolve_mode(mode)
    drives_a_browser = active == "real"

    # 0. The mode itself, first because everything below depends on it.
    checks.append(
        {
            "name": "Mode",
            "ok": drives_a_browser,
            "detail": (
                f"{active} — will drive your real browser"
                if drives_a_browser
                else f"{active} — NOT driving a real browser; "
                "acme.dev is a scripted site and nothing you do here reaches the web"
            ),
        }
    )

    # 1. Browser detection. Only what real mode would use, and only as a
    # detection result — never reported as a browser in use.
    channel = detect_channel()
    bundle = bundled_chromium_path() if not channel else None
    browser_ok = channel is not None or bundle is not None
    # In real mode, also check for a running browser with remote debugging
    # that orvima can auto-attach to (adapts to the running port).
    auto_attach = None
    if drives_a_browser:
        from .browser import _auto_detach_url
        auto_attach = _auto_detach_url()
    detail = ""
    if drives_a_browser and auto_attach:
        detail = f"detected a running browser at {auto_attach} (will attach to it)"
    elif channel:
        detail = f"would use {channel}"
    elif bundle:
        detail = "would use bundled Chromium (Playwright)"
    else:
        detail = "no Chrome/Edge/Chromium/Brave found on PATH; run 'playwright install chromium' for a real browser"
    checks.append(
        {
            "name": "Browser",
            # In demo mode a missing browser is not a problem, because nothing
            # needs one. Reporting it as a failure would be noise; reporting it
            # as ready would be the lie this check used to tell.
            "ok": browser_ok or not drives_a_browser,
            "detail": detail,
        }
    )

    # 2. Profile directory writable
    profile_dir = Path(os.environ.get("ORVIMA_PROFILE", DEFAULT_PROFILE))
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)
        test_file = profile_dir / ".orvima_write_test"
        test_file.write_text("ok")
        test_file.unlink()
        profile_ok = True
        detail = f"writable at {profile_dir}"
    except Exception as exc:
        profile_ok = False
        detail = f"not writable: {exc}"
    checks.append({"name": "Profile dir", "ok": profile_ok, "detail": detail})

    # 3. API port free
    port_free = True
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 8301))
    except OSError:
        port_free = False
    checks.append(
        {
            "name": "API port 8301",
            "ok": port_free,
            "detail": "free" if port_free else "in use (another orvima serve running?)",
        }
    )

    # 4. LLM endpoint reachable (if real mode configured)
    llm_base = os.environ.get("ORVIMA_LLM_BASE")
    llm_key = os.environ.get("ORVIMA_LLM_KEY")
    if llm_base and llm_key:
        try:
            req = urllib.request.Request(
                f"{llm_base.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {llm_key}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                llm_ok = resp.status == 200
                detail = f"reachable at {llm_base}"
        except Exception as exc:
            llm_ok = False
            detail = f"unreachable: {exc}"
    else:
        llm_ok = None
        detail = "not configured (set ORVIMA_LLM_BASE and ORVIMA_LLM_KEY for real mode)"
    checks.append({"name": "LLM endpoint", "ok": llm_ok, "detail": detail})

    # 5. MCP config validity (basic JSON check)
    mcp_config_path = Path.home() / ".config" / "orvima" / "mcp.json"
    if mcp_config_path.exists():
        try:
            json.loads(mcp_config_path.read_text())
            mcp_ok = True
            detail = f"valid JSON at {mcp_config_path}"
        except json.JSONDecodeError as exc:
            mcp_ok = False
            detail = f"invalid JSON: {exc}"
    else:
        mcp_ok = None
        detail = "not found (run 'orvima mcp' to generate a starter config)"
    checks.append({"name": "MCP config", "ok": mcp_ok, "detail": detail})

    # Print results
    all_ok = all(c["ok"] is True for c in checks if c["ok"] is not None)
    for c in checks:
        status = "✓" if c["ok"] is True else ("✗" if c["ok"] is False else "○")
        print(f"  {status} {c['name']}: {c['detail']}")

    print()
    if all_ok:
        # Say which surfaces are actually usable. In real mode with no LLM
        # configured, `orvima mcp` works and `orvima run` raises -- and a bare
        # "ready" sends the first-time user straight into the one that fails.
        llm_missing = not (os.environ.get("ORVIMA_LLM_BASE") and os.environ.get("ORVIMA_LLM_KEY"))
        if drives_a_browser and llm_missing:
            print(
                f"All checks passed — Orvima is ready for MCP ({active} mode).\n"
                "  'orvima mcp' will drive your browser now.\n"
                "  'orvima run' additionally needs ORVIMA_LLM_BASE and ORVIMA_LLM_KEY."
            )
            return 0
        print(f"All checks passed — Orvima is ready ({active} mode).")
        return 0
    if not drives_a_browser:
        # Named first, because it is the reason to care and the rest are noise
        # next to it.
        print(
            f"Some checks failed — and note that orvima is in {active} mode, so "
            "no real browser is behind it. Pass --mode real (the default) to drive one."
        )
        return 1
    print("Some checks failed — see above.")
    return 1


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="orvima",
        description="The browser your AI drives — and you can watch. Local-first, MCP-native, no cloud.",
    )
    parser.add_argument("--version", action="version", version=f"orvima {__version__}")
    # Global browser flags (work with any subcommand)
    parser.add_argument("--browser", default=None, choices=["chrome", "msedge", "brave", "chromium"],
                        help="default: autodetect your installed Chrome/Edge")
    parser.add_argument("--attach", default=None, metavar="CDP_URL",
                        help="drive an already-running browser, e.g. http://127.0.0.1:9222")
    parser.add_argument("--headless", action="store_true", help="no visible window (CI/pod-friendly)")
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

    p_bench = sub.add_parser("bench", help="measure agent-loop task pass rate (no browser needed)")
    p_bench.add_argument("--json", action="store_true", help="machine-readable summary")
    p_bench.add_argument("--shape", help="only run tasks of this shape")
    p_bench.add_argument("--out", help="write the full report to this JSON file")

    sub.add_parser("doctor", help="health check: browser, profile, port, LLM, MCP")

    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    mode = resolve_mode(getattr(args, "mode", None))
    if getattr(args, "browser", None):
        _warn_inert_browser_flag(args.browser, mode)
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
        if args.command == "bench":
            from .bench import main as bench_main

            bench_argv: list[str] = []
            if args.json:
                bench_argv.append("--json")
            if args.shape:
                bench_argv += ["--shape", args.shape]
            if args.out:
                bench_argv += ["--out", args.out]
            return bench_main(bench_argv)
        if args.command == "doctor":
            return cmd_doctor(mode)
        return 2
    except Exception as exc:  # noqa: BLE001 - friendly CLI errors
        print(f"orvima: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
