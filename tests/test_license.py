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


# --- v0.1.2 regressions -------------------------------------------------
# Each case below is a real miss observed while curating a source library
# with pkgguard as the first gate.

@pytest.mark.parametrize("lic", [
    "Limited Commercial License",
    "Limited Use License",
    "Commit-Only License",
])
def test_permissive_requires_word_boundary(lic):
    """A name that merely *contains* 'mit' must not read as permissive.

    'Li-mit-ed Commercial License' used to match the bare substring 'mit' and
    grade OK / 'Safe for commercial use' — wrong in the most dangerous
    direction, and it returned before the custom-license scan could run.
    """
    f = run_license(lic)
    assert f.grade_hint is not Grade.OK or "Permissive" not in f.title, (
        f"{lic!r} was graded permissive via substring match"
    )


@pytest.mark.parametrize("lic", ["MIT", "MIT License", "Apache-2.0", "BSD-3-Clause", "ISC"])
def test_real_permissive_still_ok(lic):
    """Word boundaries must not break genuine permissive ids."""
    f = run_license(lic)
    assert f.grade_hint is Grade.OK
    assert "Permissive" in f.title


@pytest.mark.parametrize("text", [
    "본 스킬 모음의 재판매, 유료 재배포, 유료 서비스 번들링을 금지합니다.",
    "원저작자 표기를 유지한 비상업적 공유만 허용합니다.",
    "상업적 이용 금지. 연구 목적으로만 사용하십시오.",
    "本ソフトウェアの商用利用は禁止されています。",
    "非商用目的のみ、再配布禁止。",
    "本项目仅供学习研究使用，禁止商业用途。",
    "僅供研究，禁止轉售。",
])
def test_cjk_restrictive_terms_detected(text):
    """CJK-authored LICENSE files must not slip through as unclassifiable.

    Observed miss: a Korean LICENSE explicitly banning resale and paid-service
    bundling graded ✅ OK, because the restrictive pattern was English-only.
    """
    from pkgguard.checks.license import _RESTRICTIVE
    assert _RESTRICTIVE.search(text), f"missed restrictive CJK terms in {text!r}"


@pytest.mark.parametrize("body,label", [
    ("MIT License\n\nCopyright (c) 2026 Someone\n\nPermission is hereby granted, "
     "free of charge, to any person obtaining a copy", "MIT"),
    ("Apache License, Version 2.0, January 2004", "Apache-2.0"),
    ("Redistribution and use in source and binary forms, with or without", "BSD"),
])
def test_identify_permissive_from_body(body, label):
    """SPDX=NOASSERTION + verbatim permissive body -> name it, don't stay silent."""
    ir = ItemReport(item=Item(raw="x", name="x", ecosystem=Ecosystem.PYPI))
    ir.meta["exists"] = True
    f = LicenseCheck()._identify_body(ir, body)
    assert f is not None, "permissive body not identified"
    assert label in f.title
    assert f.grade_hint is Grade.OK


def test_identify_body_ignores_unknown_text():
    """Must not guess when the body has no verbatim signature."""
    ir = ItemReport(item=Item(raw="x", name="x", ecosystem=Ecosystem.PYPI))
    assert LicenseCheck()._identify_body(ir, "All rights reserved. Contact us.") is None
    assert LicenseCheck()._identify_body(ir, "") is None
