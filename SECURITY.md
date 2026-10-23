# Orvima Security Policy — Local-First Safety and Approval Gate

> **Meta description:** Orvima security policy: local-first safety, loopback-only defaults, Sentinel approval gate, vulnerability reporting, and best practices for AI agent browser automation.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅        |
| < 0.2.0 | ❌        |

## Reporting a Vulnerability

**Do not report security vulnerabilities via public GitHub issues.**

Instead, email security@orvima.in (or create a private GitHub Security Advisory).

We will:
1. Acknowledge within 48 hours
2. Assess severity and impact
3. Develop a fix
4. Release a patch
5. Credit you (if desired)

## Security Considerations

### Browser Automation
- Orvima launches real browsers with CDP
- Never run untrusted scripts with `--mode real`
- Use `--mode demo` for untrusted input

### MCP Server
- Run behind authentication in production
- Limit network exposure
- Use HTTPS for CDP connections

### Mail/ WhatsApp Tools
- Credentials stored in environment variables
- Never commit credentials to git
- Use app passwords, not main passwords

### Safe Defaults
- Safety gates enabled by default
- Destructive actions require human approval
- Approval requests auto-expire
- No cloud dependencies by default

## Best Practices

1. **Never commit secrets** - Use `.env` files (in `.gitignore`)
2. **Run with least privilege** - Don't run as root
3. **Keep dependencies updated** - Run `pip-audit` periodically
3. **Monitor sessions** - Use the `/api/sessions` endpoint
4. **Use HTTPS in production** - Terminate TLS at reverse proxy
## Liability & Strong-Request Override

Orvima and its bundled Sentinel gate are decision aids, not guarantees.
When Sentinel flags an action (place order, delete account, enter password)
as needing human approval, the user who issues a strong override or clicks
"approve" assumes full responsibility for the consequences of that action.

The maintainers of Orvima provide this software "as-is" under the MIT
license with no warranty. Orvima will not auto-execute a hard "deny" even
on a strong request ("user requested" can lift "ask" to "allow", never
"deny"), and every override is logged with timestamp, reason, and the
tool/args signature that was allowed.

No emoji, no AI raster art, no external network calls in the safety path.

## Related Documentation

- [README](README.md) — overview and quick start.
- [API Reference](docs/api.md) — full MCP tools reference.
- [Launch Announcements](docs/launch.md)
- [Disclaimer](DISCLAIMER.md)
