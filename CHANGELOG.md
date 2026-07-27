# Changelog

All notable changes to pkgguard are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.2]

Fixes found by using pkgguard as the first gate on a 37-source curation batch
(3D/three.js, video, infra). Every item below is a *reproduced* miss, not a
speculative hardening.

### Fixed
- **Permissive-license match now respects word boundaries.** `_PERMISSIVE` used a
  bare substring test, so `"Limited Commercial License"` matched `mit` inside
  `Li·mit·ed` and graded **✅ "Safe for commercial use"** — wrong in the most
  dangerous direction. Worse, that branch returned early, so the custom-license
  scan never ran. Also affected any name containing `isc` (e.g. "disclaimer"
  text in a registry license field).

### Added
- **CJK restrictive-license detection.** The restrictive pattern was English-only,
  so a hand-written Korean/Japanese/Chinese `LICENSE` mapped to NOASSERTION and
  passed as ✅. Reproduced on a real repo whose Korean LICENSE bans resale and
  paid-service bundling — it graded ✅ OK before this change, ⚠️ WARN after.
  Korean is matched with a *trailing-negation* window (`재판매, 유료 재배포, …
  번들링을 금지합니다`), because Korean lists the prohibited acts first and
  negates once at the end — adjacency matching misses that word order.
- **Positive license identification from the LICENSE body.** GitHub reports
  NOASSERTION whenever its classifier is unsure, including for verbatim MIT text
  with an unusual copyright line. pkgguard already fetched that text but stayed
  silent unless it looked restrictive, so the repo showed only "repo exists" and
  a human had to open the file to learn it was plain MIT. Now a verbatim
  MIT/Apache/BSD/MPL/Unlicense/ISC body is named explicitly, labelled as read
  from body text rather than from SPDX. Signature-phrase matching only, so it
  cannot promote a modified or dual-licensed file by accident.

### Tests
- 95 passing (19 new: word-boundary regressions, CJK detection incl.
  permissive-phrasing false-positive guards, and body identification).

### Known gaps (not implemented — see `IMPROVEMENT-REQUEST-0.1.3.md`)
Agent-config mutation at install time, star-to-substance ratio, headline-vs-README
contradiction, default credentials, prompt-injection surface. Documented with
evidence rather than shipped as fuzzy heuristics.

## [0.1.1]

Precision + coverage fixes from real-world use (cross-checking ~230 repos).

### Added
- **Custom / NOASSERTION license detection.** When GitHub can't map a license to
  a standard SPDX id, pkgguard now reads the raw `LICENSE`/README text and flags
  non-commercial / research-only / RAIL restrictions (common for AI model repos,
  e.g. fish-speech, index-tts) instead of passing them as ✅.
- **`--policy` (opt-in) purpose check.** Flags tools whose *purpose* is ToS-abuse
  or attack (account farms, SMS/CAPTCHA-bypass, DDoS stressers, credential
  stuffers). Fires only on multiple abuse signals in an automation context;
  backs off for structurally defensive/detection tooling. Explicitly labelled a
  "policy heuristic, not a supply-chain signal."

### Changed
- **Fake-star precision.** `--deep` now suppresses reputable owners (microsoft,
  google, github, huggingface, …) and repos with real adoption (forks tracking
  stars), and downgrades a lone burst on an established repo to info. A ⚠️ now
  requires a burst on a new, thin, non-major repo — cutting false positives on
  normal viral growth while still catching bought-star repos.

### Tests
- 76 passing (9 new regression tests for the three fixes).

## [0.1.0]

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
