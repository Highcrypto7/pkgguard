# Security Policy

pkgguard is a security tool, so we hold its own behaviour to a high bar.

## Safety guarantees

- **pkgguard never executes the packages it inspects.** Existence and metadata
  checks read public registry/GitHub APIs over HTTPS. The opt-in source scan
  (`--scan`) downloads a package archive and analyses it **statically** — Python
  is parsed with `ast` (parsing does not run code), other files are
  pattern-matched. Archives are extracted in-memory with hard caps on size,
  file count and path traversal.
- **No API keys or secrets are required or transmitted.** `GITHUB_TOKEN`, if set,
  is used only as a bearer token to raise GitHub's rate limit.

## Reporting a vulnerability

If you find a security issue in pkgguard itself, please open a
[GitHub Security Advisory](https://github.com/Highcrypto7/pkgguard/security/advisories/new)
or email the maintainer rather than filing a public issue. We aim to respond
within a few days.

## Scope

pkgguard reports *signals and heuristics*, not proof. A ✅ verdict means "no red
flags found," not a guarantee of safety. Always pair automated checks with human
judgement for anything sensitive.
