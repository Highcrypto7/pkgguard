"""Adversarial robustness: weird inputs must never crash (all offline)."""

import json

from pkgguard.engine import vet
from pkgguard.models import Grade
from pkgguard.report import render_cli, render_json, render_md


def run(text, **kw):
    # offline + no cache => deterministic, no network, exercises all checks' guards
    return vet(text, offline=True, use_cache=False, **kw)


def test_empty_inputs():
    for t in ("", "   ", "\n\n\t", "###\n# just comments\n"):
        r = run(t, fmt="auto")
        assert r.items == []


def test_garbage_input_no_packages():
    r = run("!!! ??? ... === >>> @@@ \n :) :( \n", fmt="chat")
    # Either nothing, or nothing that crashes; just must not raise.
    assert isinstance(r.items, list)


def test_large_input_no_crash():
    names = "\n".join(f"pkg-{i}" for i in range(200))
    r = run(names, fmt="list", ecosystem="pypi")
    assert len(r.items) == 200
    for ir in r.items:
        assert ir.grade in (Grade.UNKNOWN, Grade.WARN)


def test_unicode_and_emoji_do_not_crash():
    r = run("requests\n日本語パッケージ\n📦emoji-pkg\nDěčín\n", fmt="list", ecosystem="pypi")
    assert isinstance(r.items, list)  # parser drops/handles non-ASCII; no raise


def test_malformed_package_json():
    for bad in ('{"dependencies":', "{not json}", "[]", "null", '{"dependencies":"oops"}'):
        r = run(bad, fmt="package-json")
        assert isinstance(r.items, list)


def test_malformed_requirements_lines():
    text = ">>>\n==1.0\n[extras]\n@@@@\nrequests===\n-r other.txt\n--index-url x\n"
    r = run(text, fmt="requirements")
    assert isinstance(r.items, list)  # no crash on junk lines


def test_very_long_name():
    r = run("a" * 5000, fmt="list", ecosystem="pypi")
    assert isinstance(r.items, list)


def test_renderers_never_crash_on_any_report():
    r = run("requests\nreqeusts\nsome/repo\n@scope/pkg", fmt="list")
    # All three renderers must produce output without raising.
    assert "items" in json.loads(render_json(r))
    assert "pkgguard report" in render_md(r)
    import io
    buf = io.StringIO()
    render_cli(r, use_color=False, stream=buf)
    assert buf.getvalue()


def test_duplicate_dedup_within_input():
    r = run("requests\nrequests\nrequests", fmt="list", ecosystem="pypi")
    assert len(r.items) == 1
