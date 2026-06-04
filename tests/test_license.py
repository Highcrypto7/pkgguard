import pytest

from pkgguard.checks.base import CheckContext
from pkgguard.checks.license import LicenseCheck
from pkgguard.http import HttpClient
from pkgguard.models import Ecosystem, Grade, Item, ItemReport


def run_license(license_str):
    ir = ItemReport(item=Item(raw="x", name="x", ecosystem=Ecosystem.PYPI))
    ir.meta["registry"] = {"license": license_str}
    ir.meta["exists"] = True
    LicenseCheck().run(ir, CheckContext(http=HttpClient(offline=True)))
    assert ir.findings, f"no license finding for {license_str!r}"
    return ir.findings[0]


@pytest.mark.parametrize("lic,label,grade", [
    ("AGPL-3.0", "AGPL", Grade.WARN),
    ("SSPL-1.0", "SSPL", Grade.WARN),
    ("Business Source License 1.1", "BUSL", Grade.WARN),
    ("CC-BY-NC-4.0", "CC-BY-NC", Grade.WARN),
    ("Sustainable Use License (fair-code)", "fair-code", Grade.WARN),
])
def test_license_traps(lic, label, grade):
    f = run_license(lic)
    assert label in f.title
    assert f.grade_hint is grade


@pytest.mark.parametrize("lic", ["MIT", "BSD-3-Clause", "Apache-2.0", "ISC"])
def test_permissive_ok(lic):
    f = run_license(lic)
    assert f.grade_hint is Grade.OK


def test_gpl_is_copyleft_warn():
    f = run_license("GPL-3.0")
    assert f.grade_hint is Grade.WARN
    assert "Copyleft" in f.title


def test_no_license_warns():
    f = run_license("")
    assert f.grade_hint is Grade.WARN
    assert "No clear license" in f.title


def test_unrecognized_does_not_drag_grade():
    f = run_license("Dual License")
    assert f.grade_hint is Grade.OK  # noted, but doesn't worsen the verdict
