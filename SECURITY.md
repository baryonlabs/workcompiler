# Security Policy

## Supported versions

| Version | Supported |
| :-- | :-- |
| `main` and the latest release | yes |
| older tags | no |

## Reporting a vulnerability

Email **hello@baryon.ai** with the subject `SECURITY: <short title>`. Do not open a public issue for
undisclosed vulnerabilities. We acknowledge within 3 business days and aim to ship a fix or
mitigation within 30 days; we credit reporters in the release notes unless asked not to.

## Scope notes

- The zero-code proxy forwards authentication headers to the upstream you configure and must be
  bound to localhost (the default). Do not expose it to a network.
- Compiled `handlers/*.py` replay recorded shell commands and file patches; treat a build like code
  you review before running it against production data.
- Telemetry is local by default and records metadata only — see `docs/TELEMETRY.md`.
