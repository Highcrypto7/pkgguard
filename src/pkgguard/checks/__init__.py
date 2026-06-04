"""Check registry.

Checks run in a fixed dependency order against each :class:`ItemReport`,
sharing the report's ``meta`` dict so later checks reuse earlier lookups
(e.g. ``existence`` resolves the GitHub repo URL that ``github_meta`` needs).

Adding a new verification axis = drop a module here and append it to
``build_checks`` in the right slot. Nothing else changes — this is the
extension seam.
"""

from __future__ import annotations

from typing import List

from .base import Check, CheckContext

__all__ = ["Check", "CheckContext", "build_checks"]


def build_checks() -> List[Check]:
    """Return all checks in dependency order.

    Order matters: existence must run before anything that reads registry
    metadata; github_meta before license/maintenance/fake_stars which read the
    fetched repo data.
    """
    from .existence import ExistenceCheck
    from .typosquat import TyposquatCheck
    from .github_meta import GitHubMetaCheck
    from .license import LicenseCheck
    from .maintenance import MaintenanceCheck
    from .vulnerabilities import VulnerabilityCheck
    from .popularity import PopularityCheck
    from .malware import MalwareSignalCheck
    from .source_scan import SourceScanCheck
    from .fake_stars import FakeStarsCheck

    return [
        ExistenceCheck(),      # 1. does it even exist? (resolves repo_url)
        TyposquatCheck(),      # 2. is it a near-miss of a popular name?
        GitHubMetaCheck(),     # 3. fetch stars/commits/license/archived
        LicenseCheck(),        # 4. license traps (needs license data)
        MaintenanceCheck(),    # 5. dead/abandoned repo (needs commit data)
        VulnerabilityCheck(),  # 6. known CVEs via OSV (needs version/ecosystem)
        PopularityCheck(),     # 7. download-count legitimacy signal
        MalwareSignalCheck(),  # 8. install-script / brand-new metadata signals
        SourceScanCheck(),     # 9. static source IOC scan (opt-in --scan)
        FakeStarsCheck(),      # 10. star inflation (needs stargazers; opt-in)
    ]
