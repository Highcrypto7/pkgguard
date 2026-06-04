"""MCP server: let an AI assistant vet its own package suggestions.

This is the "self-check" loop — an assistant (Claude, ChatGPT, Cursor, …) calls
``vet_packages`` on the names it's about to recommend and only surfaces the ones
that are real and safe. Run it with:

    pip install "pkgguard[mcp]"
    pkgguard-mcp                      # stdio transport

Then register it in your MCP client config.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional


def _build_server():
    from mcp.server.fastmcp import FastMCP

    from .engine import vet
    from .models import Grade

    mcp = FastMCP("pkgguard")

    @mcp.tool()
    def vet_packages(
        text: str,
        ecosystem: Optional[str] = None,
        format: str = "auto",
    ) -> Dict[str, Any]:
        """Vet packages/repos before installing or recommending them.

        Pass package names, a requirements.txt / package.json body, or free text
        (e.g. your own draft answer). Returns a verdict per item:
        ok / warn / danger / unknown, with the reasons. Use this to avoid
        recommending hallucinated, slopsquatted, malicious, or trap-licensed
        packages.

        Args:
            text: names, a manifest body, or free text to mine for references.
            ecosystem: optional "pypi" or "npm" hint for bare names.
            format: "auto" (default), "requirements", "package-json", "chat", "list".
        """
        report = vet(text, fmt=format, ecosystem=ecosystem)
        return report.to_dict()

    @mcp.tool()
    def is_safe_to_install(name: str, ecosystem: Optional[str] = None) -> Dict[str, Any]:
        """Quick yes/no gate for a single package or owner/repo.

        Returns {safe, grade, summary}. ``safe`` is False for danger/warn.
        """
        report = vet(name, fmt="list", ecosystem=ecosystem)
        if not report.items:
            return {"safe": False, "grade": "unknown", "summary": "could not parse name"}
        ir = report.items[0]
        return {
            "safe": ir.grade is Grade.OK,
            "grade": ir.grade.value,
            "summary": ir.summary,
        }

    return mcp


def main(argv: Optional[List[str]] = None) -> int:
    try:
        mcp = _build_server()
    except ImportError:
        sys.stderr.write(
            "pkgguard-mcp requires the MCP SDK. Install it with:\n"
            "    pip install 'pkgguard[mcp]'\n"
        )
        return 1
    mcp.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
