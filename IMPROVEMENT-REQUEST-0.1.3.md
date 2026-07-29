# Improvement requests (open)

Gaps observed while using pkgguard as the **first gate** on a real curation
workflow (a 37-source intake batch: 3D/three.js, video tooling, AI infra).

Each entry records the **concrete repo that exposed it** and why it was *not*
shipped in 0.1.2. The bar for shipping a check here is deliberately high: this
codebase already treats false positives as a first-class failure (see the
`fake_stars` and `policy` docstrings), and a noisy check that cries wolf on
normal repos is worse than no check — it trains the operator to skim past ⚠️.

---

## 1. Agent-config mutation at install time ★ highest value

**Observed:** a 26.7k-star MIT tool (`tirth8205/code-review-graph`) whose bare
`install` subcommand auto-detects ~14 AI tool configurations (Claude Code, Codex,
Cursor, Windsurf, Zed, Gemini CLI, Copilot, Kiro, …), writes MCP entries and
platform-native hooks into each, **and injects its own instructions into the
platform rules files.** pkgguard graded it ✅ OK — correctly, by every existing
axis: MIT, alive, real adoption, no malware IOC.

**Why it matters here specifically.** pkgguard's whole pitch is "vet what your AI
recommended before you install". An installer that silently rewrites the config
of *every agent on the machine* — including the rules files that steer those
agents — is the most on-brand risk class imaginable for this tool, and no
existing check looks at it. This is not hypothetical supply-chain theory; it is
a documented, advertised feature of a popular package.

**Why not shipped:** detecting it from README text alone is unreliable. Any
legitimate MCP server says "add this to your config". The meaningful distinction
is *auto-detect and write to many, unprompted* vs *instruct the user to add one
entry*, and that is hard to separate without inspecting the package's own
install code.

**Suggested approach:** extend `source_scan` (already opt-in `--scan`, already
downloads the archive) rather than adding a README heuristic. Look for writes to
known agent-config paths — `.claude/`, `CLAUDE.md`, `.cursor/`, `.codex/`,
`mcp.json`, `.windsurf/`, `AGENTS.md` — in install/postinstall entry points.
Grade WARN with the specific paths listed. File writes are concrete evidence;
README prose is not.

---

## 2. Star-to-substance ratio (complements `fake_stars`)

**Observed:** `nexu-io/html-video` — 4,184★ and 525 forks against **8
contributors, 139 commits, one month old**. `cocoindex` and `code-review-graph`
show the same shape (heavy promotion) but with genuine substance underneath
(2,014 and 734 commits, 88 and 98 contributors), so the ratio *discriminates*.

**Why not shipped:** `fake_stars` already suppresses on forks-track-stars, and
this signal would partly overlap. Needs calibration against a corpus before it
earns a ⚠️ — shipped badly it would flag every successful young project.

**Suggested approach:** info-level only, never WARN on its own; surface as a
context line ("4.2k★ but 8 contributors / 139 commits / 34 days old") so a human
can weigh it. Consider folding into `popularity` rather than a new check.

---

## 3. Headline-vs-README contradiction

**Observed:** `malisper/pgrust` — the GitHub description claims "now passing 100%
of the Postgres regression tests"; the README's own text concedes that build is
**"not yet published"** and states "not production-ready yet... not performance
optimized yet". A curator reading only the description records a false capability.

**Why not shipped:** genuine NLP-shaped problem. Regex on "not yet published" /
"not production ready" would fire on the many honest projects that say so
plainly in a Status section — punishing candour.

**Suggested approach:** only flag when a *superlative in the description*
("100%", "faster than", "production-ready") is contradicted by a negation of the
same claim in the README. Low precision otherwise; probably info-level.

---

## 4. Default credentials / bind-all in deployable services

**Observed:** `Usagi-org/ai-goofish-monitor` ships a web UI with documented
default credentials `admin/admin123` and a documented run command binding
`0.0.0.0:8000`. Its final merged commit before archiving was a path-traversal
fix — so pinned forks carry a known hole.

**Why not shipped:** narrow scope (only applies to self-hosted service repos),
and the evidence lives in README/compose files rather than package metadata.

**Suggested approach:** cheap, high-precision regex over README + any
`docker-compose*.yml`: default-credential pairs and `0.0.0.0` binds appearing
together. WARN with both facts quoted. Low false-positive risk because both
signals must co-occur.

---

## 5. Prompt-injection surface (agent-facing tools)

**Observed:** `nexu-io/html-video` exposes a "paste a link → video" path that
fetches an **arbitrary URL server-side and routes its content into the agent's
prompt**. Feeding it an untrusted page means untrusted text reaches the model.

**Why not shipped:** this is an architectural property, not a metadata one, and
would need real dataflow understanding to detect reliably.

**Suggested approach:** possibly out of scope for pkgguard. If pursued, keep it
documentation-only — a note in the README about what to look for when the
package is meant to be driven by an agent.

---

## 6. Archived-repo wording

**Currently:** `Usagi-org/ai-goofish-monitor` correctly produced
`⚠️ WARN — Repository is archived`. Working as intended.

**Small improvement:** the message could state the operational consequence —
*read-only forever; no issues or PRs will ever be accepted, so you own every
future fix* — rather than only the fact. Wording change, no logic.

---

## Meta: what this batch confirmed about the tool's role

pkgguard's first gate held up. It caught, unaided: PolyForm-Noncommercial behind
`NOASSERTION` (×2), AGPL and GPL copyleft, an archived repo, and produced zero
DANGER false alarms across 30 repos.

What it could not do — and what 0.1.2 partially closed — is **positively identify**
a license rather than merely flagging suspicion, and **read a license that isn't
in English**. Both matter because the operator's failure mode is not "misses a
threat"; it is "gives an answer so incomplete that the human stops trusting the
tool and reads every LICENSE by hand anyway."

---

## ✅ Closed in 0.2.0 — multilingual license detection

Not on the original list, and the most important item in it. Measuring coverage
against 15 non-English licenses returned **0/15 detected**: the restrictive
pattern was English-only, so a hand-written `LICENSE` in Spanish, Russian or
Thai mapped to `NOASSERTION` and passed as ✅. For a tool that answers "can I use
this commercially?", staying silent on a whole language is not a soft gap — it
is a wrong answer, in the dangerous direction, for most of the planet.

Now 25 languages, proximity-based so word order (Korean trailing negation,
German split verbs, RTL scripts) is handled by one rule rather than per-language
phrase lists. 0/15 → 15/15, with paired permissive-phrasing tests per language
and 0 false positives against the real LICENSE files of React, Kubernetes, Rust,
Django, PyTorch and others.

**Still open from this line of work:**
- **Report localisation.** Detection is multilingual; findings are still written
  in English. A Korean or Brazilian developer gets a correct verdict with an
  English explanation. Deliberate scope call — the verdict is the load-bearing
  part — but worth revisiting if non-English adoption grows.
- **The `--policy` purpose check is still English-only.** Its abuse vocabulary
  (account farms, stressers, credential stuffers) has the same blind spot the
  license check just fixed. Lower priority: abuse tooling is marketed in English
  far more consistently than licenses are written in it, but the gap is real and
  the `license_i18n` structure is directly reusable.
- **Language coverage is vocabulary, not grammar** — Bengali, Swahili, Tagalog,
  Malay and others are absent simply because nobody has added the two word lists
  yet. This is the cheapest possible contribution and a good first issue.

---

## ✅ Partially closed in 0.3.0 — agent-skill scanning (`--skills`)

Item #1 (agent-config mutation) is **half** closed. The new `skill_scan` check
detects writes to `.claude/`, `CLAUDE.md`, `mcp.json`, `.cursor/` **inside a
SKILL.md**, plus three shapes that were not on the original list at all:
credential exfiltration, stealth instructions, and encoded payloads.

**What the real-world audit showed (21 skill repos from the source library):**
zero malicious skills — and **two low-risk true positives that expose the
remaining precision gap**:

- `alexzio00/sovereign-skills` — `Save to ~/.claude/collab-audits/YYYY-MM-DD.md`
  → writing its *own output* under `.claude/`, not touching configuration.
- `addyosmani/agent-skills` — `Add the following to your project's .mcp.json`
  → the standard, manual MCP install instruction every legitimate server ships.

**So the distinction called out in item #1 is still unsolved:** *"auto-detect and
write to many, unprompted"* vs *"tell the user to add one entry"*. The current
rule cannot tell them apart and grades both MEDIUM.

**Still open, refined:**
- **Separate data writes from config writes.** `.claude/<something>/output.md` is
  a skill storing results; `.claude/settings.json` or a rules file is a skill
  changing how every agent behaves. Path shape distinguishes them cheaply.
- **Separate imperative from instructional.** "Add the following to your config"
  addresses the *human*; "auto-detect every agent config and inject" addresses
  the *agent*. Second person + a manual-step framing is the signal.
- **Item #1's original suggestion still stands for packages** (not skills):
  extend `source_scan` to look for these paths in install/postinstall entry
  points, where a file write is concrete evidence rather than prose.

**Also learned (process, not product):** the first `skill_scan` implementation
paired signals document-wide and produced 5 false positives on `anthropics/skills`
and `obra/superpowers` while every synthetic unit test passed. **Synthetic tests
cannot validate a precision-critical heuristic — only a real corpus can.** Any
future check of this kind should be run against a known-good corpus before it
ships.
