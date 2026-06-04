# Changelog

All notable changes to pkgguard are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — unreleased

Initial release.

### Added
- Input parsing for plain lists, `requirements.txt`, `package.json`, and free
  chat text (mines `pip/npm install` commands, GitHub links, code spans, lists).
- Existence verification against PyPI, npm, and GitHub (the core slopsquatting /
  hallucination signal); ambiguous names are checked against both registries.
- Typosquat / slopsquat similarity detection against a curated popular-package list.
- License-trap detection (AGPL, SSPL, BUSL, CC-BY-NC, fair-code, no-license, copyleft).
- Maintenance check (archived / disabled / deprecated / long-abandoned).
- Metadata-based malware signals (install scripts, freshly-registered look-alikes,
  no auditable source repo).
- Opt-in fake-star / popularity-inflation heuristics (`--deep`).
- Known-vulnerability (CVE) check via OSV.dev across all ecosystems.
- Download-count popularity / legitimacy signal (PyPI / npm).
- Homoglyph typosquat detection (`dj4ng0` → `django`).
- crates.io, Go modules and RubyGems support (Cargo.toml / Gemfile / go.mod).
- On-disk response cache with offline replay (`--no-cache` / `--cache-ttl` / `--clear-cache`).
- GitHub Action, pre-commit hook, and an MCP server (`pkgguard-mcp`).
- File-path positional args and multi-file input (`pkgguard requirements.txt package.json`).
- `✅ ⚠️ ❌ ❔` verdicts with a "worst finding wins" aggregator.
- CLI with stdin / file / argument input, JSON & Markdown output, CI-friendly
  exit codes (`--fail-on`), and a Windows-safe UTF-8 console.
- Zero hard dependencies (stdlib only); optional `rich` for colour.

### Hardened (post adversarial review)
- Free-text parsing no longer turns prose words ("Note that…") into phantom
  packages, captures `pip install` inside backticks, ignores `-r requirements.txt`
  and trailing prose, keeps scoped npm names from code spans, and refuses to
  silently truncate non-ASCII names.
- Disk cache tolerates corrupt / old-schema entries without crashing.
- Verified: 59 tests pass; 100% benchmark accuracy; 0 false positives on 50
  popular real packages.
