# Improvement requests for 0.1.3

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
