from pkgguard.models import (
    Ecosystem, Finding, Grade, Item, ItemReport, Report, Severity,
)
from pkgguard.report import finalize


def make(*grades):
    ir = ItemReport(item=Item(raw="x", name="x", ecosystem=Ecosystem.PYPI))
    for i, g in enumerate(grades):
        ir.add(Finding("c%d" % i, Severity.INFO, "t%d" % i, "", g))
    return finalize(ir)


def test_worst_finding_wins():
    assert make(Grade.OK, Grade.WARN, Grade.OK).grade is Grade.WARN
    assert make(Grade.OK, Grade.WARN, Grade.DANGER).grade is Grade.DANGER
    assert make(Grade.OK, Grade.OK).grade is Grade.OK


def test_unknown_between_ok_and_warn():
    assert make(Grade.OK, Grade.UNKNOWN).grade is Grade.UNKNOWN
    assert make(Grade.UNKNOWN, Grade.WARN).grade is Grade.WARN


def test_no_findings_is_unknown():
    ir = ItemReport(item=Item(raw="x", name="x"))
    assert finalize(ir).grade is Grade.UNKNOWN


def test_ok_summary_prefers_existence():
    ir = ItemReport(item=Item(raw="x", name="x", ecosystem=Ecosystem.PYPI))
    ir.add(Finding("existence", Severity.INFO, "Exists on PyPI", "", Grade.OK))
    ir.add(Finding("license", Severity.LOW, "Unrecognized license", "", Grade.OK))
    finalize(ir)
    assert ir.summary == "Exists on PyPI"


def test_report_exit_codes():
    danger = Report(items=[make(Grade.DANGER)])
    warn = Report(items=[make(Grade.WARN)])
    ok = Report(items=[make(Grade.OK)])
    assert danger.exit_code() == 2
    assert warn.exit_code() == 1
    assert ok.exit_code() == 0
