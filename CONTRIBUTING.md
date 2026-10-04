# Contributing to Orvima

Thanks for your interest in contributing! Orvima is a local-first browser agent — every contribution helps make AI-driven browsing safer and more accessible.

## Quick Start

```bash
git clone https://github.com/Sachitt-AV-08/orvima.git
cd orvima
uv venv && uv pip install -e '.[dev]'
uv run pytest          # all tests green, fast, offline
uv run orvima demo     # try the offline tour
```

## Development Guidelines

### Code Style
- **Ruff** for linting/formatting (`uv run ruff check src tests`)
- **Type hints** required on all public functions
- **Docstrings** on all public classes/functions (Google style)
- **No global state** — prefer dependency injection

### Testing
- **All tests must pass** before PR: `uv run pytest`
- **New features need tests** — demo-mode fixtures preferred (no browser needed)
- **Real-mode tests** live in `tests/test_real_mode.py` (headless Chromium)

### Commit Messages
- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`
- Keep subjects under 72 chars
- Reference issues: `fix: selector rot on login form (fixes #42)`

### Pull Requests
- **One feature/fix per PR** — small, reviewable changes
- **Tests + lint must pass** before review
- **Update docs** if user-facing behavior changes
- **Screenshots/GIFs** for UI changes

## Architecture Overview

| Module | Responsibility |
|--------|----------------|
| `src/orvima/browser.py` | BrowserController - Chrome/Edge/Brave with verify-first ops |
| `src/orvima/demo.py` | DemoBrowser — offline simulator for CI/demos |
| `src/orvima/tools.py` | `browse_*` tools as pure dict-in/dict-out functions |
| `src/orvima/planner.py` | `LLMPlanner` + `DemoPlanner` (adaptive step-planner) |
| `src/orvima/agent.py` | Sessions, EventBus, AgentLoop (snapshot→decide→act→verify) |
| `src/orvima/api.py` | FastAPI + SSE (live frames, transcript, controls) |
| `src/orvima/mcp_server.py` | MCP stdio binding (v1/v2 compatible) |
| `src/orvima/cli.py` | argparse CLI with demo/serve/mcp/run/doctor |

## Adding a New Tool

1. Add `tool_browse_newtool` function in `src/orvima/tools.py`
2. Add to `TOOLS` tuple and `TOOL_NAMES` set
3. Add `ref` support via `_resolve()` helper
4. Add structured error with `_error()` + candidates
5. Add test in `tests/test_orvima.py` (`test_tool_contract`)
6. Update `src/orvima/demo.py` for parity

## Running Tests

```bash
# All tests (offline + real-mode fixtures)
uv run pytest

# Just offline demo tests
uv run pytest tests/test_orvima.py

# Real-mode fixture tests (headless Chromium)
uv run pytest tests/test_real_mode.py
```

## Code of Conduct

Be respectful. Constructive criticism welcome. Harassment, discrimination, and toxic behavior not tolerated.

## License

By contributing, you agree your contributions will be licensed under the MIT License.