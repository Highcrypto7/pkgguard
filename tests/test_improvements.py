"""Regression tests for the 2026-07-01 improvement request (3 blind spots)."""

import pkgguard.github as ghmod
from pkgguard.checks.base import CheckContext
from pkgguard.checks.fake_stars import _classify
from pkgguard.checks.license import _RESTRICTIVE
from pkgguard.checks.policy import PolicyCheck
from pkgguard.http import HttpClient
from pkgguard.models import Ecosystem, Grade, Item, ItemReport


# --- #1 custom / NOASSERTION license -------------------------------------

def test_restrictive_license_regex_matches_non_commercial():
    assert _RESTRICTIVE.search("Personal, non-commercial use is permitted")
    assert _RESTRICTIVE.search("Any Commercial use requires a separate license")
    assert _RESTRICTIVE.search("for research purposes only")
    assert _RESTRICTIVE.search("Licensed under CC BY-NC 4.0")


def test_restrictive_license_regex_ignores_permissive():
    mit = ("Permission is hereby granted, free of charge, to any person obtaining "
           "a copy of this software to deal in the Software without restriction")
    apache = ("Apache License Version 2.0. You may reproduce and distribute copies "
              "of the Work in any medium, with or without modifications.")
    assert not _RESTRICTIVE.search(mit)
    assert not _RESTRICTIVE.search(apache)


# --- #3 fake-star precision (pure decision) ------------------------------

def test_fake_stars_suppresses_reputable_owner():
    assert _classify(100000, 5, "microsoft", 30)[0] == "suppress"
    assert _classify(50000, 0, "huggingface", 10)[0] == "suppress"


def test_fake_stars_suppresses_real_adoption():
    # forks track stars -> real usage, not bought
    assert _classify(20000, 500, "someorg", 30)[0] == "suppress"


def test_fake_stars_warns_new_thin_unknown():
    assert _classify(8000, 3, "unknownguy", 40)[0] == "warn"


def test_fake_stars_downgrades_old_thin_to_info():
    assert _classify(8000, 3, "unknownguy", 900)[0] == "info"


# --- #2 policy (abuse vs defensive) --------------------------------------

def _policy_report(readme, monkeypatch, desc=""):
    monkeypatch.setattr(ghmod, "fetch_readme", lambda http, o, r: readme)
    ir = ItemReport(item=Item(raw="x", name="o/r", ecosystem=Ecosystem.GITHUB))
    ir.meta["github_resolved"] = {"owner": "o", "repo": "r"}
    ir.meta["github"] = {"description": desc}
    ctx = CheckContext(http=HttpClient(offline=False), policy=True)
    PolicyCheck().run(ir, ctx)
    return ir


def test_policy_flags_account_farm(monkeypatch):
    readme = ("Bulk account creator with SMS verification bypass and anti-detect "
              "browser. Automated mass account generator using 5sim for phone "
              "verification bypass. For educational purposes only.")
    ir = _policy_report(readme, monkeypatch, desc="gmail account creator")
    assert ir.findings, "abuse tool should be flagged"
    assert ir.findings[0].grade_hint in (Grade.WARN, Grade.DANGER)
    assert "policy heuristic" in ir.findings[0].detail.lower()


def test_policy_suppresses_defensive_tool(monkeypatch):
    readme = ("Sigma detection rules for the blue team. SIEM content to detect "
              "credential stuffing and password spraying attacks. Threat "
              "intelligence, incident response and forensics for defenders.")
    ir = _policy_report(readme, monkeypatch, desc="detection rules")
    assert not ir.findings, "defensive tooling must not be flagged"


def test_policy_single_mention_not_flagged(monkeypatch):
    readme = "A web framework. Includes a rate limiter to help mitigate DDoS."
    ir = _policy_report(readme, monkeypatch)
    assert not ir.findings  # single passing mention, defensive context
