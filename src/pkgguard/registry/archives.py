"""Safely fetch and read text files out of a package's published archive.

Used by the opt-in source scan. SAFETY IS THE WHOLE POINT here:

* we NEVER execute or import any downloaded code — we only read bytes;
* extraction is in-memory with hard caps on archive size, per-file size, total
  bytes and file count (zip-bomb / resource-exhaustion guard);
* archive members are filtered for path traversal and absolute paths;
* only text-ish source files are read.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from typing import Dict, Optional

from ..http import HttpClient

MAX_ARCHIVE_BYTES = 20 * 1024 * 1024   # don't even read archives bigger than this
PER_FILE_BYTES = 300_000               # read at most this much per file
TOTAL_BYTES = 3 * 1024 * 1024          # ... and this much across the whole archive
MAX_FILES = 150

_INTERESTING = (
    ".py", ".js", ".cjs", ".mjs", ".ts", ".json", ".cfg", ".sh", ".bash",
    ".bat", ".ps1", ".toml",
)
_INTERESTING_NAMES = ("setup.py", "setup.cfg", "pyproject.toml", "package.json")


def _wanted(path: str) -> bool:
    low = path.lower()
    return low.endswith(_INTERESTING) or low.rsplit("/", 1)[-1] in _INTERESTING_NAMES


def _safe_member_name(name: str) -> bool:
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    parts = name.replace("\\", "/").split("/")
    return ".." not in parts


def _read_tar(body: bytes) -> Dict[str, str]:
    out: Dict[str, str] = {}
    total = 0
    try:
        tf = tarfile.open(fileobj=io.BytesIO(body), mode="r:*")
    except Exception:
        return out
    try:
        for member in tf:
            if len(out) >= MAX_FILES or total >= TOTAL_BYTES:
                break
            if not member.isfile() or not _safe_member_name(member.name):
                continue
            if not _wanted(member.name) or member.size > PER_FILE_BYTES:
                continue
            try:
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                data = fh.read(PER_FILE_BYTES)
            except Exception:
                continue
            total += len(data)
            out[member.name] = data.decode("utf-8", errors="replace")
    finally:
        tf.close()
    return out


def _read_zip(body: bytes) -> Dict[str, str]:
    out: Dict[str, str] = {}
    total = 0
    try:
        zf = zipfile.ZipFile(io.BytesIO(body))
    except Exception:
        return out
    try:
        for info in zf.infolist():
            if len(out) >= MAX_FILES or total >= TOTAL_BYTES:
                break
            if info.is_dir() or not _safe_member_name(info.filename):
                continue
            if not _wanted(info.filename) or info.file_size > PER_FILE_BYTES:
                continue
            try:
                with zf.open(info) as fh:
                    data = fh.read(PER_FILE_BYTES)
            except Exception:
                continue
            total += len(data)
            out[info.filename] = data.decode("utf-8", errors="replace")
    finally:
        zf.close()
    return out


def _download(http: HttpClient, url: str) -> Optional[bytes]:
    try:
        resp = http.get(url, accept="*/*")
    except Exception:
        return None
    if not resp.ok or not resp.body or len(resp.body) > MAX_ARCHIVE_BYTES:
        return None
    return resp.body


def _pypi_archive_url(http: HttpClient, name: str) -> str:
    data = http.get_json_or_none(f"https://pypi.org/pypi/{name}/json")
    if not isinstance(data, dict):
        return ""
    urls = data.get("urls") or []
    sdist = next((u for u in urls if u.get("packagetype") == "sdist"), None)
    chosen = sdist or (urls[0] if urls else None)
    return (chosen or {}).get("url", "")


def _npm_archive_url(http: HttpClient, name: str) -> str:
    from urllib.parse import quote
    data = http.get_json_or_none(f"https://registry.npmjs.org/{quote(name, safe='@/')}")
    if not isinstance(data, dict):
        return ""
    latest = (data.get("dist-tags") or {}).get("latest")
    ver = (data.get("versions") or {}).get(latest, {})
    return ((ver.get("dist") or {}).get("tarball")) or ""


def fetch_source_files(http: HttpClient, ecosystem, name: str) -> Dict[str, str]:
    """Return {path: text} of source files from the package archive, or {}."""
    from ..models import Ecosystem

    if ecosystem is Ecosystem.PYPI:
        url = _pypi_archive_url(http, name)
    elif ecosystem is Ecosystem.NPM:
        url = _npm_archive_url(http, name)
    else:
        return {}
    if not url:
        return {}
    body = _download(http, url)
    if not body:
        return {}
    if url.lower().endswith((".whl", ".zip")):
        return _read_zip(body)
    return _read_tar(body)
