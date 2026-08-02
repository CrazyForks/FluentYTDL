# Security Policy

## Supported versions

FluentYTDL is updated frequently because it depends on external websites and media tools.

| Version | Security support |
|---|---|
| Latest stable release | Supported |
| Pre-release builds | Best effort |
| Older releases | Not supported; reproduce on the latest stable release first |

## Report a vulnerability privately

Do not open a public issue for a suspected vulnerability.

Use [GitHub's private vulnerability reporting form](https://github.com/SakuraForgot/FluentYTDL/security/advisories/new). If the form is unavailable, contact the current maintainer through the contact method listed on the [SakuraForgot GitHub profile](https://github.com/SakuraForgot) without publishing exploit details.

Include:

- affected version and component
- impact and required attacker access
- reproducible steps or a minimal proof of concept
- whether credentials, cookies, the updater, external binaries, or subprocess execution are involved
- suggested mitigation, if known

Never include live credentials, reusable cookies, tokens, or private user data. Use synthetic or revoked test data.

## Response process

The maintainer will acknowledge a complete report when it has been reviewed, validate the affected versions, coordinate a fix and release, and publish an advisory when users can take action. Timelines depend on severity, reproducibility, and upstream dependencies.

Good-faith research against code and systems you own or are authorized to test is welcome. Do not test against other users, accounts, services, or infrastructure without permission.
