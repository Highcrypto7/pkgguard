"""Opt-in source-level malware heuristics (``--scan`` / deep_source).

Closes the one dimension dedicated scanners (GuardDog/Snyk/Socket) had over
pkgguard: actually looking at the *code*. We do it **statically and without ever
executing anything** — Python is parsed with ``ast`` (parsing ≠ running), other
files are pattern-matched. The strongest signal is dangerous behaviour at
*install time* (setup.py / npm install hooks), which is how most package
malware detonates.

This is heavier (it downloads the package archive), so it is off by default.
For exhaustive source analysis, also run DataDog's GuardDog.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Dict, List, Set, Tuple

from ..models import Ecosystem, Finding, Grade, Severity
from ..registry.archives import fetch_source_files
from .base import Check, CheckContext

# Sensitive targets that legitimate libraries rarely touch.
_SENSITIVE = re.compile(
    r"(\.ssh/|id_rsa|/etc/passwd|\.aws/credentials|AWS_SECRET|"
    r"ANTHROPIC_API_KEY|OPENAI_API_KEY|\.npmrc|\.pypirc|wallet\.dat|"
    r"keychain|\.bash_history)",
    re.IGNORECASE,
)
_OBFUSCATION = re.compile(r"(b64decode|base64|fromCharCode|atob|\\x[0-9a-fA-F]{2}){3,}")

# Test/example/doc files legitimately contain scary-looking patterns; skip them.
_SKIP_PATH = re.compile(
    r"(^|/)(tests?|__tests__|test|spec|examples?|docs?|fixtures?|benchmarks?|"
    r"\.github)(/|$)|(^|/)(conftest|test_[^/]*|[^/]*_test)\.[a-z]+$|\.min\.js$",
    re.IGNORECASE,
)


def _py_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_py_call_name(node.value)}.{node.attr}" if node.value else node.attr
    return ""


def _scan_python(path: str, text: str) -> Set[str]:
    """Return a set of IOC category tags found in a Python file."""
    tags: Set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Fall back to coarse text matching if it won't parse.
        if re.search(r"\b(eval|exec)\s*\(", text):
            tags.add("dynamic-exec")
        return _augment_text(tags, text)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _py_call_name(node.func)
            tail = name.rsplit(".", 1)[-1]
            if tail in ("eval", "exec", "compile") or name == "__import__":
                tags.add("dynamic-exec")
            if name in ("os.system", "os.popen") or tail in (
                "Popen", "call", "run", "check_output", "check_call", "popen"
            ):
                tags.add("subprocess")
            if tail in ("b64decode", "decompress", "loads") and (
                "base64" in name or "marshal" in name or "zlib" in name
            ):
                tags.add("obfuscation")
            if name in ("socket.socket",) or tail in ("urlopen", "urlretrieve") or (
                tail in ("get", "post") and "request" in name.lower()
            ):
                tags.add("network")
    return _augment_text(tags, text)


def _augment_text(tags: Set[str], text: str) -> Set[str]:
    if _SENSITIVE.search(text):
        tags.add("sensitive-access")
    if _OBFUSCATION.search(text):
        tags.add("obfuscation")
    return tags


def _scan_js(path: str, text: str) -> Set[str]:
    tags: Set[str] = set()
    if re.search(r"\beval\s*\(|new\s+Function\s*\(", text):
        tags.add("dynamic-exec")
    if re.search(r"child_process|\.exec\s*\(|\.spawn\s*\(|execSync", text):
        tags.add("subprocess")
    if re.search(r"Buffer\.from\([^)]*base64|atob\s*\(", text):
        tags.add("obfuscation")
    if re.search(r"require\(['\"](https?|net|dns|dgram)['\"]\)|fetch\(|XMLHttpRequest", text):
        tags.add("network")
    return _augment_text(tags, text)


def _scan_install_hooks(text: str) -> List[str]:
    """package.json install hooks that run shell/download/eval -> high risk."""
    hits = []
    try:
        data = json.loads(text)
    except Exception:
        return hits
    scripts = data.get("scripts") or {}
    if not isinstance(scripts, dict):
        return hits
    danger = re.compile(
        r"(curl|wget|node\s+-e|eval|base64|child_process|powershell|chmod\s|/dev/tcp|"
        r"https?://)",
        re.IGNORECASE,
    )
    for hook in ("preinstall", "install", "postinstall"):
        cmd = scripts.get(hook)
        if isinstance(cmd, str) and danger.search(cmd):
            hits.append(f"{hook}: {cmd[:80]}")
    return hits


_TAG_LABEL = {
    "dynamic-exec": "dynamic code execution (eval/exec)",
    "subprocess": "spawns a subprocess",
    "obfuscation": "obfuscated/encoded payload",
    "network": "network access",
    "sensitive-access": "reads credentials/keys/sensitive files",
}


class SourceScanCheck(Check):
    id = "source_scan"

    def applies(self, report, ctx: CheckContext) -> bool:
        return (
            getattr(ctx, "deep_source", False)
            and not ctx.offline
            and report.meta.get("exists") is True
            and report.item.ecosystem in (Ecosystem.PYPI, Ecosystem.NPM)
        )

    def run(self, report, ctx: CheckContext) -> None:
        eco = report.item.ecosystem
        files = fetch_source_files(ctx.http, eco, report.item.name)
        if not files:
            report.meta["source_scan"] = "unavailable"
            return

        install_time: List[str] = []      # IOCs that run at install time (worst)
        runtime_tags: Set[str] = set()
        evidence: Dict[str, str] = {}      # tag -> example file
        dropper_files: List[str] = []      # files mixing obfuscation + exec/network
        scanned = 0

        for path, text in files.items():
            low = path.lower()
            if low.endswith("package.json"):
                install_time += _scan_install_hooks(text)
                continue
            if _SKIP_PATH.search(path):
                continue  # test/example/doc code is allowed to look scary
            scanned += 1
            if low.endswith((".js", ".cjs", ".mjs", ".ts")):
                tags = _scan_js(path, text)
            elif low.endswith(".py"):
                tags = _scan_python(path, text)
            else:
                tags = _augment_text(set(), text)

            # Dropper signature must occur within a SINGLE file to count.
            if "obfuscation" in tags and ("dynamic-exec" in tags or "network" in tags):
                dropper_files.append(path)

            is_install = low.endswith("setup.py") or low.endswith((".sh", ".bat", ".ps1"))
            for t in tags:
                evidence.setdefault(t, path)
                if is_install and t in ("dynamic-exec", "subprocess", "network", "obfuscation"):
                    install_time.append(f"{path}: {_TAG_LABEL[t]}")
                else:
                    runtime_tags.add(t)

        report.meta["source_scan"] = {
            "files_scanned": scanned,
            "install_time": install_time,
            "dropper_files": dropper_files,
            "runtime_tags": sorted(runtime_tags),
        }

        # Install-time code execution / download is the malware hallmark -> DANGER.
        if install_time:
            sample = "; ".join(install_time[:3])
            report.add(Finding(
                self.id, Severity.CRITICAL,
                "Executes code at install time",
                f"Install-time behaviour is how package malware detonates: {sample}. "
                f"Do not install without reading the source.",
                Grade.DANGER,
            ))

        # Strong runtime combo: obfuscation + (exec or network) in ONE file.
        if dropper_files:
            report.add(Finding(
                self.id, Severity.HIGH,
                "Obfuscated payload combined with exec/network",
                f"Decoded/obfuscated data feeding code execution or network calls "
                f"in {dropper_files[0]} — a common dropper pattern.",
                Grade.WARN,
            ))
        elif "sensitive-access" in runtime_tags:
            report.add(Finding(
                self.id, Severity.MEDIUM,
                "Accesses credentials / sensitive files",
                f"References secrets/keys (e.g. {evidence.get('sensitive-access', '?')}). "
                f"Verify this is expected.",
                Grade.WARN,
            ))
        elif runtime_tags:
            labels = ", ".join(_TAG_LABEL[t] for t in sorted(runtime_tags))
            report.add(Finding(
                self.id, Severity.LOW,
                f"Source uses: {labels}",
                "Common in legitimate packages too; noted for awareness.",
                Grade.OK,
            ))
