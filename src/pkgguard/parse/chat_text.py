"""Mine package/repo references out of free-form text.

This is pkgguard's headline trick: paste whatever ChatGPT/Claude told you and we
pull out the things you'd actually ``install``. We deliberately favour
*high-signal* sources over tokenizing prose, so we don't flag every English
word as a hallucinated package:

1. install commands  (``pip install x``, ``npm i y``, ``yarn add z`` ...)
2. GitHub links / ``owner/repo`` slugs
3. inline code spans  (`` `package-name` ``)
4. bullet / numbered list items whose first token is a plausible name

Tokens found via an install command carry a known ecosystem; everything else
stays ``UNKNOWN`` and is resolved later by trying both registries.
"""

from __future__ import annotations

import re
from typing import List

from ..models import Ecosystem, Item
from .normalize import (
    GITHUB_SLUG_RE,
    looks_like_npm_name,
    looks_like_pypi_name,
    strip_repo_suffix,
)

# Words that look like package names but are almost always prose/flags.
# Compared case-insensitively (see usage), so list lowercase forms only.
_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "you", "your", "use", "using",
    "install", "run", "add", "npm", "pip", "pip3", "yarn", "pnpm", "python",
    "python3", "node", "npx", "package", "packages", "library", "libraries",
    "module", "modules", "import", "from", "require", "https", "http", "github",
    "com", "www", "via", "then", "next", "first", "also", "note", "make", "sure",
    "check", "ensure", "create", "set", "setup", "configure", "consider", "try",
    "see", "here", "these", "those", "they", "them", "can", "will", "should",
    "must", "need", "needs", "want", "want", "now", "after", "before", "once",
    "out", "into", "let", "lets", "get", "got", "have", "has", "are", "was",
    "all", "any", "some", "most", "more", "less", "such", "like", "good",
    "great", "best", "popular", "recommended", "example", "step", "steps",
    "finally", "additionally", "however", "but", "because", "since", "while",
    "when", "where", "what", "which", "who", "how", "why", "yes", "okay",
    "go", "run", "ran", "it", "do", "does", "did", "to", "in", "on", "of",
    "or", "if", "is", "be", "by", "as", "at", "we", "i",
}

# Tokens that are file paths / manifests, not package names.
_FILE_EXTS = (".txt", ".json", ".toml", ".cfg", ".ini", ".lock", ".md", ".yml",
              ".yaml", ".lockb", ".sh", ".py", ".js", ".ts")

_GITHUB_URL = re.compile(
    r"github\.com/([A-Za-z0-9][\w.-]*)/([A-Za-z0-9][\w.-]*)", re.IGNORECASE
)

# pip install a b c   |  pip3 install -U a   |  python -m pip install a
_PIP_INSTALL = re.compile(
    r"(?:python[0-9.]*\s+-m\s+)?pip[0-9]?\s+install\s+(?P<args>[^\n;&|]+)",
    re.IGNORECASE,
)
# npm install a  |  npm i a  |  yarn add a  |  pnpm add a  |  pnpm install a
_NPM_INSTALL = re.compile(
    r"(?:npm\s+(?:install|i)|yarn\s+add|pnpm\s+(?:add|install))\s+(?P<args>[^\n;&|]+)",
    re.IGNORECASE,
)

_CODE_SPAN = re.compile(r"`([^`\n]{1,120})`")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
_LEADING_TOKEN = re.compile(r"[A-Za-z0-9@][A-Za-z0-9._/@-]*")


def _install_args(blob: str) -> List[str]:
    out = []
    skip_next = False
    for tok in blob.split():
        if skip_next:           # argument of -r/-c/--requirement etc.
            skip_next = False
            continue
        if tok in ("-r", "-c", "--requirement", "--constraint", "-e", "--editable"):
            skip_next = True
            continue
        if tok.startswith("-"):  # other flags like -U, --upgrade
            continue
        # Strip surrounding quotes/backticks AND trailing sentence punctuation.
        tok = tok.strip("\"'`.,;:()[]")
        if not tok:
            continue
        # Skip manifest/file arguments and VCS URLs (handled by the URL scan).
        low = tok.lower()
        if low.endswith(_FILE_EXTS) or "://" in tok or low.startswith("git+"):
            continue
        scoped = tok.startswith("@")
        tok = tok.split("[", 1)[0]  # drop pip extras: name[extra]
        if scoped:
            # @scope/name@version -> keep @scope/name, drop trailing @version
            at = tok.find("@", 1)
            if at != -1:
                tok = tok[:at]
        else:
            # strip version operators: name==1, name>=2, name@1
            tok = re.split(r"[=<>~!@ ]", tok, maxsplit=1)[0]
        tok = tok.strip("\"'`.,;:()[]")
        if tok:
            out.append(tok)
    return out


def parse_chat_text(
    text: str,
    source: str = "chat-text",
    default_ecosystem: Ecosystem = Ecosystem.UNKNOWN,
) -> List[Item]:
    items: List[Item] = []
    seen = set()

    def add(name: str, eco: Ecosystem, raw: str, repo_url: str = None) -> None:
        name = name.strip()
        key = f"{eco}:{name.lower()}"
        if not name or key in seen:
            return
        seen.add(key)
        items.append(
            Item(raw=raw, name=name, ecosystem=eco, repo_url=repo_url, source=source)
        )

    # 1. GitHub URLs (highest signal for repo recommendations)
    for m in _GITHUB_URL.finditer(text):
        owner, repo = m.group(1), strip_repo_suffix(m.group(2).rstrip(").,"))
        add(
            f"{owner}/{repo}",
            Ecosystem.GITHUB,
            m.group(0),
            repo_url=f"https://github.com/{owner}/{repo}",
        )

    # 2. install commands -> known ecosystem. Stopword-filter the args so
    #    trailing prose ("... then run it") isn't mistaken for packages.
    for m in _PIP_INSTALL.finditer(text):
        for tok in _install_args(m.group("args")):
            if tok.lower() not in _STOPWORDS and looks_like_pypi_name(tok):
                add(tok, Ecosystem.PYPI, m.group(0).strip())
    for m in _NPM_INSTALL.finditer(text):
        for tok in _install_args(m.group("args")):
            if tok.lower() in _STOPWORDS:
                continue
            if looks_like_npm_name(tok) or tok.startswith("@"):
                add(tok, Ecosystem.NPM, m.group(0).strip())

    # 3. inline code spans
    for m in _CODE_SPAN.finditer(text):
        tok = m.group(1).strip().strip(".,;:")
        is_slug = bool(GITHUB_SLUG_RE.match(tok))
        is_scoped = tok.startswith("@") and looks_like_npm_name(tok)
        # Skip multi-word code (commands); install regexes already handle those.
        if (" " in tok) or ("/" in tok and not is_slug and not is_scoped):
            continue
        if is_slug:
            owner, repo = tok.split("/", 1)
            add(
                f"{owner}/{strip_repo_suffix(repo)}",
                Ecosystem.GITHUB,
                tok,
                repo_url=f"https://github.com/{owner}/{strip_repo_suffix(repo)}",
            )
        elif is_scoped:
            add(tok, Ecosystem.NPM, tok)
        elif tok.lower() not in _STOPWORDS and looks_like_pypi_name(tok):
            add(tok, default_ecosystem, tok)

    # 4. bullet / numbered list items
    for line in text.splitlines():
        m = _LIST_ITEM.match(line)
        if not m:
            continue
        raw_body = m.group(1).strip()
        emphasized = raw_body[:1] in ("`", "*", "_")  # `pkg` or **pkg**
        body = raw_body.strip("`*_")
        tm = _LEADING_TOKEN.match(body)
        if not tm:
            continue
        tok = tm.group(0).rstrip(".,:")
        if tok.lower() in _STOPWORDS:
            continue
        rest = body[len(tm.group(0)):].strip()
        # Prose guard: a capitalized plain word followed by more text is a
        # sentence ("Note that ..."), not a package. Keep lowercase names,
        # names with -_./digits, deliberately emphasized names, or standalone.
        package_ish = (not tok[:1].isupper()) or any(c in tok for c in "-_./0123456789")
        if not (package_ish or emphasized or not rest):
            continue
        if GITHUB_SLUG_RE.match(tok):
            owner, repo = tok.split("/", 1)
            add(
                f"{owner}/{strip_repo_suffix(repo)}",
                Ecosystem.GITHUB,
                tok,
                repo_url=f"https://github.com/{owner}/{strip_repo_suffix(repo)}",
            )
        elif tok.startswith("@") and looks_like_npm_name(tok):
            add(tok, Ecosystem.NPM, body[:80])
        elif looks_like_pypi_name(tok):
            add(tok, default_ecosystem, body[:80])

    return items
