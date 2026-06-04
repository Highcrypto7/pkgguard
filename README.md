<h1 align="center">pkgguard</h1>

<p align="center">
  <strong>Vet the packages and repos your AI assistant recommended — <em>before</em> you install them.</strong>
</p>

<p align="center">
  <a href="https://github.com/Highcrypto7/pkgguard/actions"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/Highcrypto7/pkgguard/ci.yml?branch=main"></a>
  <a href="https://pypi.org/project/pkgguard-cli/"><img alt="PyPI" src="https://img.shields.io/pypi/v/pkgguard-cli"></a>
  <img alt="Python" src="https://img.shields.io/pypi/pyversions/pkgguard-cli">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"></a>
  <img alt="No API key" src="https://img.shields.io/badge/API%20key-not%20required-blue">
  <img alt="Ecosystems" src="https://img.shields.io/badge/ecosystems-8-purple">
</p>

---

Your AI coding assistant just gave you a `pip install` line or a list of
"recommended libraries." **Some of those names don't exist. Some are one keystroke
away from a popular package. Some are real but AGPL-licensed, abandoned, riddled
with CVEs, or propped up by bought stars.** Installing them is how modern
supply-chain attacks start.

`pkgguard` checks every name in one command and tells you which are safe — across
**PyPI, npm, crates.io, Go, RubyGems, Packagist, NuGet and pub.dev** — with **no
API key** and **without executing a single line** of the packages it inspects.

```console
$ pkgguard requests reqeusts beautifulsoup-4 django==3.0.0 super-fake-pkg-zzz

      ✅ OK      requests           Exists on PyPI · 1.6B downloads/mo · Apache-2.0
      ⚠️ WARN    django             31 known CVEs in 3.0.0 — upgrade
      ❌ DANGER  reqeusts           Resembles 'requests' but does not exist — slopsquat bait
      ❌ DANGER  beautifulsoup-4    Hallucination — real package is 'beautifulsoup4'
      ❌ DANGER  super-fake-pkg-zzz Not found on PyPI or npm — likely invented

1 ok  1 warn  3 danger  0 unknown          # exit code 2 → fails your CI
```

> Existing tools (Snyk, Socket, OSV) scan dependencies you've **already chosen**.
> **pkgguard answers the newer, earlier question:** *"the thing the LLM just told
> me to install — is it even real, and should I trust it?"*

---

## 🩸 Why this matters: the slopsquatting epidemic

LLMs invent package names. A peer-reviewed **[USENIX Security 2025 study](https://www.usenix.org/system/files/conference/usenixsecurity25/sec25cycle1-prepub-742-spracklen.pdf)**
generated 2.23M code samples and found:

- **19.7%** of AI-generated samples referenced a **package that does not exist** (up to **~33%** for some models).
- When the same prompt was repeated, **43% of hallucinated names appeared *every single time*** — they are **predictable**.

That predictability is the attack. An adversary asks an LLM what it hallucinates,
**pre-registers those exact names** on PyPI/npm with malware inside, and waits for
the next developer to copy-paste the assistant's answer into a terminal. Security
researchers named it **slopsquatting**, and it is
[already happening in the wild](https://socket.dev/blog/slopsquatting-how-ai-hallucinations-are-fueling-a-new-class-of-supply-chain-attacks).

As AI assistants become the default way developers discover dependencies, **the
moment an AI hands you a package list is now a front-line security boundary.**
pkgguard guards exactly that moment.

---

## ⚡ What it checks

Every package/repo runs through an ordered pipeline of **10 checks**. The worst
finding sets the verdict, so a single command gives you one clear answer per item.

| Check | What it catches |
|---|---|
| **Existence** | Names that don't exist on any registry — the core hallucination / slopsquat signal |
| **Typosquat + homoglyph** | 1–2 edits from a popular package (`reqeusts`→`requests`) and digit/letter look-alikes (`dj4ng0`→`django`) |
| **Known vulnerabilities** | Open CVEs/advisories for the resolved version via [OSV.dev](https://osv.dev) (GHSA / PyPA / RustSec / RubySec…) |
| **Source malware scan** *(opt-in `--scan`)* | Statically inspects the package archive for install-time code execution, obfuscated payloads, `child_process`/`os.system`, credential access — **without ever running it** |
| **License traps** | AGPL / SSPL / BUSL / CC-BY-NC / fair-code / "no license" — landmines for commercial products |
| **Maintenance** | Archived, disabled, deprecated, or long-abandoned projects |
| **Popularity** | Download counts as a legitimacy signal |
| **Fake stars** *(opt-in `--deep`)* | Star-count inflation: implausible growth and burst-buying patterns |
| **Repo health** | GitHub stars / last commit / license / archived state for the upstream repo |
| **Malware metadata** | npm install scripts, freshly-registered look-alikes, packages with no auditable source |

**Supported ecosystems:** PyPI · npm · crates.io · Go modules · RubyGems · Packagist · NuGet · pub.dev — plus GitHub repos.

---

## 📦 Install

```bash
pip install pkgguard-cli            # core — zero dependencies, no API key
pip install "pkgguard-cli[rich]"    # + prettier coloured tables
pip install "pkgguard-cli[mcp]"     # + MCP server for AI assistants
```

The PyPI distribution is **`pkgguard-cli`**; the command it installs is **`pkgguard`**.
Requires Python 3.9+. The core engine is **stdlib-only**.

## 🚀 Quick start

```bash
# a few names
pkgguard requests numpy pandas

# a manifest — auto-detected: requirements.txt, package.json, Cargo.toml, Gemfile, go.mod
pkgguard requirements.txt
pkgguard package.json Cargo.toml          # several at once

# 🌟 the headline trick: paste whatever ChatGPT / Claude told you
pkgguard --stdin < chat.txt
pbpaste | pkgguard --stdin                # macOS

# go deeper
pkgguard requirements.txt --scan          # download + statically scan source
pkgguard some/repo --deep                 # add fake-star analysis
```

pkgguard mines free text for `pip install …` / `npm i …` commands, GitHub links,
inline `` `code spans` `` and bullet lists — and is careful **not** to flag plain
English prose as packages. Names whose ecosystem isn't stated are checked against
**both** PyPI and npm.

### Machine-readable output & CI

```bash
pkgguard -f requirements.txt --json               # JSON to stdout
pkgguard -f requirements.txt --markdown -o report.md
pkgguard -f requirements.txt --fail-on warn       # non-zero exit gates your pipeline
```

Exit codes: `0` clean · `1` a warning (`--fail-on warn`) · `2` a danger.

---

## 🔌 Integrations

<details open>
<summary><strong>pre-commit hook</strong></summary>

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/Highcrypto7/pkgguard
  rev: v0.1.0
  hooks:
    - id: pkgguard          # auto-runs on requirements*.txt and package.json
```
</details>

<details>
<summary><strong>GitHub Action</strong></summary>

```yaml
# .github/workflows/pkgguard.yml
- uses: Highcrypto7/pkgguard@v1
  with:
    files: "requirements.txt package.json"
    fail-on: danger
```
</details>

<details>
<summary><strong>MCP server — let the assistant check its own answer</strong></summary>

```bash
pip install "pkgguard-cli[mcp]"
pkgguard-mcp          # exposes vet_packages() and is_safe_to_install() over MCP
```

Register `pkgguard-mcp` in Claude Desktop / Cursor and the assistant can vet a
package **before it ever recommends it** — stopping slopsquatting at the source.
</details>

---

## 🥊 How it compares

Other tools are excellent at scanning dependencies you've **already chosen**.
pkgguard is the fast first gate at the moment an AI (or a teammate) hands you a list.

| | **pkgguard** | sloppy-joe | depscope | GuardDog | Snyk / Socket |
|---|:--:|:--:|:--:|:--:|:--:|
| Hallucination / existence | ✅ | ✅ | ✅ | – | ~ |
| Typosquat + homoglyph | ✅ | ✅ | ✅ | ~ | ~ |
| Known CVEs (OSV) | ✅ | ✅ | ✅ | – | ✅ |
| Static source malware scan | ✅ | – | – | ✅ | ✅ |
| License traps (AGPL / NC / …) | ✅ | ~ | – | – | ✅ |
| Maintenance / dead repo | ✅ | ✅ | ~ | – | ~ |
| Fake-star inflation | ✅ | – | – | – | – |
| **Paste a chat answer (free text)** | ✅ | – | – | – | – |
| **MCP self-check for assistants** | ✅ | – | ✅ | – | – |
| Ecosystems | **8** | 2 | 19 | 5 | many |
| Open source · No key · Offline-degraded | ✅ | ✅ | partial | ✅ | – |

**pkgguard's edge:** the widest set of checks in a single zero-key OSS gate,
framed around AI output — including license and fake-star checks the others skip,
and a "paste the chat answer" workflow nobody else has. *Honest gap:*
GuardDog/Snyk/Socket do deeper source-level malware analysis; run them alongside
pkgguard for defence in depth.

---

## 📊 Proof

- **Benchmark: 100% accuracy** on a labeled set of 30 PyPI/npm packages (15 real, 15 hallucinated/typosquat). Reproduce: `python benchmark/run_benchmark.py`. See [BENCHMARK.md](BENCHMARK.md).
- **Zero false positives** when vetting the 50 most popular real PyPI/npm packages.
- **67 automated tests**, deterministic and offline.

## 🧭 Verdicts

- ✅ **OK** — exists and nothing concerning found.
- ⚠️ **WARN** — usable, but read the caveat (license, CVE, staleness, look-alike…).
- ❌ **DANGER** — doesn't exist, or a strong risk signal. Don't install without verifying.
- ❔ **UNKNOWN** — couldn't determine (offline / rate-limited). Honest about what it didn't check.

## 🔐 Design principles

- **No API key, ever.** Public registry/GitHub metadata over HTTPS. Set `GITHUB_TOKEN` only to raise rate limits.
- **No code execution.** The source scan parses with `ast` and pattern-matching; it never imports or runs package code, and extracts archives in-memory with strict size/path guards.
- **Honest by default.** "Couldn't check" is ❔, never a silent ✅.
- **Fast & offline-friendly.** On-disk response cache; a previous run answers even with no network.

## ⚠️ Limitations

- Heuristics, not proof. A ✅ means "no red flags found," not a security guarantee.
- The typosquat reference list is a curated set of popular packages, not all of every registry.
- Fake-star and source-scan checks are opt-in and intentionally conservative — they complement, not replace, dedicated tools (StarScout, GuardDog).
- Unauthenticated GitHub is limited to ~60 requests/hour; set `GITHUB_TOKEN` for large runs.

## 🗺️ Roadmap

- More ecosystems (Maven, Hex, CPAN)
- Large-scale benchmark against the [trendmicro/slopsquatting](https://github.com/trendmicro/slopsquatting) dataset
- VS Code extension
- Deeper static source analysis

## 🤝 Contributing

Issues and PRs welcome — a new ecosystem is just a registry adapter, and a new
check is a single module (see `src/pkgguard/checks/`). Run `pytest` before
submitting.

## 📄 License

MIT — see [LICENSE](LICENSE). Built to make the AI coding era a little safer.
