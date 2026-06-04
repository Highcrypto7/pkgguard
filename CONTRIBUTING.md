# Contributing to pkgguard

Thanks for helping make the AI coding era safer! Contributions of all sizes are welcome.

## Getting started

```bash
git clone https://github.com/Highcrypto7/pkgguard
cd pkgguard
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## Architecture (where things live)

Everything flows through one pipeline:

```
raw text --(parse)--> [Item] --(checks)--> [Finding] --(aggregate)--> Report --(render)
```

- `src/pkgguard/parse/` — turn input (lists, manifests, chat text) into `Item`s.
- `src/pkgguard/registry/` — one adapter per registry (existence + metadata).
- `src/pkgguard/checks/` — one module per verification axis. **This is the extension seam.**
- `src/pkgguard/report/` — aggregation + CLI / Markdown / JSON renderers.

### Add a new check
Create a class in `src/pkgguard/checks/`, subclass `Check`, implement `run()`,
and register it in `checks/__init__.py:build_checks()` at the right position.

### Add a new ecosystem
Add a `fetch_<eco>()` adapter in `src/pkgguard/registry/`, add the enum value in
`models.py`, and wire it into `checks/existence.py`'s `_FETCHERS`. No engine
changes needed.

## Guidelines

- Keep the **core engine dependency-free** (stdlib only); heavy/optional features go behind extras.
- **Never execute** inspected package code. Static analysis only.
- Favour **precision over recall** — a false ❌ on a real package erodes trust faster than a missed edge case.
- Add a test for every fix or feature. Run `pytest` before opening a PR.

## License

By contributing you agree your work is licensed under the project's MIT License.
