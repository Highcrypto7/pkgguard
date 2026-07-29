"""Agent-skill security check (opt-in: ``--skills``).

Skills became the dominant install surface for AI agents during 2026, and the
security story did not keep up. An independent audit of 2,857 published skills
found roughly 12% malicious, and Trail of Bits demonstrated bypasses of the
existing malicious-skill detectors using prompt injection and payloads hidden in
compiled bytecode.

**Why the existing checks miss this entirely.** ``source_scan`` downloads a
PyPI/npm archive and parses code. A skill is neither: it ships as a GitHub
folder containing ``SKILL.md``, and its payload is usually *the instructions
themselves* — plain English telling the agent to read a credential file and post
it somewhere. No code to parse, no archive to download, nothing for an AST
walker to find.

That is also what makes a skill different from a library. A library runs in a
sandbox you chose; a skill runs **with your agent's permissions, on your
machine, next to your credentials**, and the agent follows it because following
instructions is the whole point. Installing one off a leaderboard is closer to
running a stranger's shell script than to adding a dependency.

**Precision over recall, deliberately.** Skills legitimately mention files,
shells and URLs, so single signals are worthless. The rules here fire only on
*combinations* that have no benign reading — a credential target together with
network egress, or an instruction to act without telling the user. A noisy
check here would be worse than none: it trains the operator to skim past ⚠️,
which is the exact failure mode this tool exists to prevent.

Never a hard ❌ on its own: a hit is evidence with the line quoted, for a human
to judge.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from ..models import Finding, Grade, Severity
from .base import Check, CheckContext

# --- signal vocabulary ------------------------------------------------------
#
# ★Lesson from the first implementation (kept here because it is the whole
# design constraint): matching two words *anywhere in the same document* is
# useless. A legitimate API-reference skill mentions ANTHROPIC_API_KEY in one
# paragraph and a URL in another, and a document-wide pairing calls that
# credential exfiltration. Validating against real skills (anthropics/skills,
# obra/superpowers) produced 5 findings, all false. Every rule below therefore
# requires the signals to co-occur inside a short window, and the vocabulary is
# narrowed to imperative forms — instructions, not prose that mentions a topic.

_WINDOW = 200  # chars between the two concepts; roughly a sentence or two

# Reading a secret. Narrowed to *file/secret targets*, not env-var names in
# prose (an API-key name appears in every API document ever written).
_CREDENTIAL = re.compile(
    r"(\.ssh/|id_rsa|id_ed25519|\.aws/credentials|\.npmrc|\.pypirc|"
    r"wallet\.dat|keychain|credentials\.json|"
    r"seed\s?phrase|mnemonic|private key file|"
    r"(?:cat|read|open|load|dump|exfiltrate|collect)\s+[^\r\n]{0,40}?"
    r"(?:\.env\b|secret|credential|token|api[_ ]?key))",
    re.IGNORECASE,
)

# Sending data off the machine — imperative forms only.
_EGRESS = re.compile(
    r"((?:curl|wget)\s+[^\r\n]*(?:-d\b|--data|-F\b|--post)|"
    r"(?:post|send|upload|exfiltrate|transmit)\s+(?:it|them|this|the\s+"
    r"(?:file|contents|output|data|result|key|token))\s+to\b|"
    r"requests\.post\(|fetch\([^)]{0,80}POST|"
    r"webhook\.(?:site|com)|https?://[^\s)\"']*(?:collect|exfil|steal|log|beacon))",
    re.IGNORECASE,
)

# Telling the agent to keep a step off the user's screen. Requires an explicit
# user-directed phrase — a bare adverb like "silently" is far too common.
_STEALTH = re.compile(
    r"(do\s*n[o']t\s+(?:tell|inform|mention|show|notify|alert)\s+the\s+user|"
    r"without\s+(?:telling|informing|notifying|asking)\s+the\s+user|"
    r"without\s+(?:the\s+)?user'?s?\s+(?:knowledge|consent|permission)|"
    r"hide\s+(?:this|the)\s+(?:step|output|command|action)\s+from\s+the\s+user|"
    r"(?:skip|bypass)\s+(?:the\s+)?(?:confirmation|approval)\s+(?:prompt|step|dialog)|"
    r"suppress\s+(?:all\s+)?(?:output|logging)\s+so\s+the\s+user)",
    re.IGNORECASE,
)

# Writing into the configuration that steers every agent on the machine.
# Config *paths* only — a bare "*.md" filename is documentation, not config.
_AGENT_CONFIG = re.compile(
    r"(\.claude/|(?:^|[\s/`])CLAUDE\.md|(?:^|[\s/`])AGENTS\.md|\.cursor/|"
    r"\.codex/|\.windsurf/|mcp\.json|claude_desktop_config\.json|\.gemini/)",
    re.IGNORECASE,
)
# Imperative write verbs, and only ones that imply *modifying the user's* files.
_WRITES = re.compile(
    r"((?:write|append|inject|add)\s+[^\r\n]{0,50}?\s(?:to|into)\b|"
    r"modify\s+the\s+user|patch\s+the|overwrite|auto[- ]?(?:detect|install)\s+"
    r"[^\r\n]{0,40}config)",
    re.IGNORECASE,
)

# Encoded payload sitting inside a file whose purpose is human-readable text.
_ENCODED = re.compile(r"[A-Za-z0-9+/]{160,}={0,2}")
_DECODE_CALL = re.compile(r"(base64\s+-d|b64decode|atob\(|FromBase64String)", re.IGNORECASE)


def _near(a: Optional[re.Match], b: Optional[re.Match], window: int = _WINDOW) -> bool:
    """True when two matches sit within ``window`` characters of each other."""
    if not a or not b:
        return False
    return abs(a.start() - b.start()) <= window


def _find_near(text: str, first: re.Pattern, second: re.Pattern
               ) -> Optional[Tuple[re.Match, re.Match]]:
    """First (a, b) pair from the two patterns that co-occur within the window."""
    for a in first.finditer(text):
        lo, hi = max(0, a.start() - _WINDOW), a.start() + _WINDOW
        b = second.search(text, lo, hi)
        if b:
            return a, b
    return None


def _find_near_end(text: str, first: "re.Pattern", second: "re.Pattern"
                   ) -> Optional[Tuple["re.Match", "re.Match"]]:
    """Like :func:`_find_near`, but measured from the END of the first match.

    A base64 blob is itself hundreds of characters long, so a window anchored on
    its start never reaches the ``| base64 -d`` that follows it.
    """
    for a in first.finditer(text):
        b = second.search(text, a.end(), a.end() + _WINDOW)
        if b:
            return a, b
    return None


def _line_of(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    line = text[start: end if end != -1 else len(text)]
    return " ".join(line.split())[:150]


def analyze_skill(text: str) -> List[Tuple[str, Severity, str, str]]:
    """Return [(rule_id, severity, headline, evidence_line)] for one SKILL.md.

    Every rule needs its signals to co-occur *within a short window*. Nothing
    fires on a single vocabulary hit, and nothing fires on two hits that merely
    live in the same document.
    """
    out: List[Tuple[str, Severity, str, str]] = []
    if not text or not text.strip():
        return out

    # 1. The canonical exfiltration shape: read a secret, then send it — close
    #    enough together to be one instruction rather than two topics.
    pair = _find_near(text, _CREDENTIAL, _EGRESS)
    if pair:
        out.append((
            "credential-exfil", Severity.HIGH,
            "Skill reads a secret and sends it off-machine in the same instruction",
            _line_of(text, pair[0].start()),
        ))

    # 2. Explicitly telling the agent to keep the user out of the loop.
    stealth = _STEALTH.search(text)
    if stealth:
        out.append((
            "stealth-instruction", Severity.HIGH if pair else Severity.MEDIUM,
            "Skill instructs the agent to act without informing the user",
            _line_of(text, stealth.start()),
        ))

    # 3. Rewriting the config that steers every agent on the machine.
    cfgpair = _find_near(text, _AGENT_CONFIG, _WRITES)
    if cfgpair:
        out.append((
            "agent-config-write", Severity.MEDIUM,
            "Skill writes into agent configuration or rules files",
            _line_of(text, cfgpair[0].start()),
        ))

    # 4. An encoded blob inside an instruction file, with something to decode it.
    encpair = _find_near_end(text, _ENCODED, _DECODE_CALL)
    if encpair:
        out.append((
            "encoded-payload", Severity.HIGH,
            "Skill contains an encoded blob plus a decode step",
            _line_of(text, encpair[0].start())[:80] + " …",
        ))
    return out


class SkillScanCheck(Check):
    """Fetch a repo's SKILL.md files and look for malicious instruction shapes."""

    id = "skills"

    def applies(self, report, ctx: CheckContext) -> bool:
        return (
            getattr(ctx, "skills", False)
            and not ctx.offline
            and bool(report.meta.get("github_resolved"))
        )

    def run(self, report, ctx: CheckContext) -> None:
        from ..github import fetch_skill_files

        gh = report.meta["github_resolved"]
        files = fetch_skill_files(ctx.http, gh["owner"], gh["repo"])
        if not files:
            return

        report.meta["skills"] = {"count": len(files)}
        hits: Dict[str, List[Tuple[str, Severity, str, str]]] = {}
        for path, text in files.items():
            found = analyze_skill(text)
            if found:
                hits[path] = found

        if not hits:
            report.add(Finding(
                self.id, Severity.INFO,
                f"Agent skills present ({len(files)} SKILL.md), no malicious shape found",
                "Scanned the skill instructions for credential exfiltration, stealth "
                "directives, agent-config writes and encoded payloads. Nothing matched. "
                "This is a heuristic, not an audit — read SKILL.md before installing.",
                Grade.OK,
            ))
            return

        worst = max(
            (sev for found in hits.values() for _, sev, _, _ in found),
            key=lambda s: (s is Severity.HIGH, s is Severity.MEDIUM),
        )
        lines = []
        for path, found in sorted(hits.items()):
            for rule, sev, headline, evidence in found:
                lines.append(f"[{rule}] {path}: {headline} — \"{evidence}\"")
        report.meta["skills"]["findings"] = lines

        report.add(Finding(
            self.id, worst,
            f"Skill security: {len(lines)} suspicious instruction(s) in {len(hits)} file(s)",
            "A skill runs with your agent's permissions, on your machine, next to your "
            "credentials — and the agent follows its instructions by design. "
            + " | ".join(lines[:4])
            + (f" | (+{len(lines) - 4} more)" if len(lines) > 4 else "")
            + " — Read the SKILL.md yourself before installing; that reading is the "
              "entire security model.",
            Grade.WARN,
        ))
