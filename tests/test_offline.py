"""Offline behaviour: no network, no crashes, honest UNKNOWN/WARN verdicts."""

from pkgguard.engine import vet
from pkgguard.models import Grade


def test_offline_does_not_crash_and_is_honest():
    report = vet("requests\nreqeusts\nnumpy", fmt="list", ecosystem="pypi",
                 offline=True, use_cache=False)
    assert len(report.items) == 3
    # Nothing can be confirmed absent offline -> no false DANGER from existence.
    for ir in report.items:
        assert ir.grade in (Grade.UNKNOWN, Grade.WARN)
        assert not ir.meta.get("_check_errors"), ir.meta.get("_check_errors")


def test_offline_typosquat_warns_not_dangers():
    report = vet("reqeusts", fmt="list", ecosystem="pypi", offline=True, use_cache=False)
    ir = report.items[0]
    # Looks like 'requests' but existence unknown -> WARN, never DANGER.
    assert ir.grade is Grade.WARN
    assert any("requests" in f.title for f in ir.findings)


def test_offline_render_json_roundtrip():
    import json
    from pkgguard.report import render_json
    report = vet("flask", fmt="list", ecosystem="pypi", offline=True, use_cache=False)
    data = json.loads(render_json(report))
    assert "items" in data and "summary" in data
