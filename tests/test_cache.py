"""Disk cache: stores definitive results, replays them offline, respects caps."""

import os

from pkgguard.cache import DiskCache
from pkgguard.http import HttpClient, OfflineError


def test_put_get_roundtrip(tmp_path):
    c = DiskCache(path=str(tmp_path / "c.json"), ttl=3600)
    c.put("http://x/a", 200, b'{"ok":true}', {"content-type": "application/json"})
    c.flush()
    c2 = DiskCache(path=str(tmp_path / "c.json"), ttl=3600)
    hit = c2.get("http://x/a")
    assert hit and hit["status"] == 200 and "ok" in hit["body"]


def test_skips_transient_and_oversized(tmp_path):
    c = DiskCache(path=str(tmp_path / "c.json"), ttl=3600)
    c.put("http://x/500", 500, b"err", {})       # transient -> not cached
    c.put("http://x/big", 200, b"x" * (DiskCache.MAX_BODY_BYTES + 1), {})  # too big
    c.put("http://x/404", 404, b"nope", {})       # definitive negative -> cached
    assert c.get("http://x/500") is None
    assert c.get("http://x/big") is None
    assert c.get("http://x/404") is not None


def test_ttl_expiry(tmp_path):
    c = DiskCache(path=str(tmp_path / "c.json"), ttl=0)  # everything is stale
    c.put("http://x/a", 200, b"{}", {})
    assert c.get("http://x/a") is None


def test_offline_client_serves_from_cache(tmp_path):
    cache = DiskCache(path=str(tmp_path / "c.json"), ttl=3600)
    cache.put("https://pypi.org/pypi/requests/json", 200, b'{"info":{}}', {})
    client = HttpClient(offline=True, cache=cache)
    resp = client.get("https://pypi.org/pypi/requests/json")  # no network, no raise
    assert resp.status == 200


def test_corrupt_cache_entry_does_not_crash(tmp_path):
    # An old-schema / partial entry lacking "status" must be ignored, not crash.
    cache = DiskCache(path=str(tmp_path / "c.json"), ttl=3600)
    cache._data["https://x/y"] = {"ts": 9999999999, "body": "{}"}  # no status
    client = HttpClient(offline=True, cache=cache)
    try:
        client.get("https://x/y")  # should raise OfflineError, NOT KeyError
        assert False, "expected OfflineError"
    except OfflineError:
        pass


def test_offline_client_without_cache_raises():
    client = HttpClient(offline=True)
    try:
        client.get("https://pypi.org/pypi/requests/json")
        assert False, "expected OfflineError"
    except OfflineError:
        pass
