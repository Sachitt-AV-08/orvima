# Orvima Quickstart

Get Orvima running in 5 minutes.

## 1. Install

```bash
git clone https://github.com/Sachitt-AV-08/orvima.git
cd orvima
pip install -e .
```

## 2. Configure

Set environment variables (PowerShell example):

```powershell
$env:ORVIMA_MAIL_HOST = "smtp.gmail.com"
$env:ORVIMA_MAIL_PORT = "587"
$env:ORVIMA_MAIL_USER = "your-email@gmail.com"
$env:ORVIMA_MAIL_PASS = "your-app-password"
$env:ORVIMA_MAIL_USE_TLS = "1"
```

## 3. Start MCP Server

```bash
orvima mcp --mode real --browser chromium
```

Or start the SaaS API for CDP session deployment:

```bash
python -m uvicorn orvima.saas_api:app --host 0.0.0.0 --port 8000
```

## 4. Deploy a Session

```bash
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{"headless": true, "ttl_minutes": 60}'
```

Returns a CDP URL like `http://localhost:9222`. Connect with Playwright:

```python
from playwright.sync_api import sync_playwright
pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]
page.goto('https://example.com')
```

## 5. Verify

- Health check: `http://localhost:8000/health`
- List sessions: `http://localhost:8000/api/sessions`
- Orvima docs: `docs/api.md`