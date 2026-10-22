# Contributing to Orvima

Thank you for contributing to Orvima! We welcome contributions from everyone.

## How to Contribute

### 1. Fork & Clone

```bash
git clone https://github.com/Sachitt-AV-08/orvima.git
cd orvima
```

### 2. Create a Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/your-fix-name
```

### 3. Make Changes

- Follow the existing code style
- Run tests before committing
- Update documentation if needed

### 4. Run Quality Checks

```bash
# Format and lint
ruff format .
ruff check .

# Run tests
pytest
```

### 5. Commit & Push

```bash
git add .
git commit -m "feat: add your feature description"
git push origin feat/your-feature-name
```

### 6. Open a Pull Request

- Fill out the PR template
- Link related issues
- Request review

## Code Style

- Python 3.11+
- Ruff for formatting and linting
- Type hints required for new code
- Docstrings for public functions

## Adding a New MCP Tool

1. Create tool in `src/orvima/tools/`
2. Register in `src/orvima/tools/__init__.py`
3. Add tests in `tests/`
4. Update `docs/api.md`

## Reporting Bugs

- Use GitHub Issues
- Include steps to reproduce
- Include environment details (OS, Python version, browser)
- Include error logs

## Feature Requests

- Use GitHub Issues with "enhancement" label
- Describe the problem, not just the solution
- Explain the use case

## Questions?

Open a GitHub Discussion or issue.