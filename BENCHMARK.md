# pkgguard benchmark

- entries: 30  (scored: 30, unknown/skipped: 0)
- **accuracy: 100%**  ·  precision: 100%  ·  recall: 100%
- detected bad: 15/15  ·  false positives on good: 0/15

| name | eco | label | verdict | correct |
|---|---|---|---|---|
| `requests` | pypi | good | OK | ✅ |
| `numpy` | pypi | good | OK | ✅ |
| `pandas` | pypi | good | OK | ✅ |
| `flask` | pypi | good | OK | ✅ |
| `django` | pypi | good | OK | ✅ |
| `fastapi` | pypi | good | OK | ✅ |
| `scikit-learn` | pypi | good | OK | ✅ |
| `pillow` | pypi | good | OK | ✅ |
| `sqlalchemy` | pypi | good | OK | ✅ |
| `pytest` | pypi | good | OK | ✅ |
| `react` | npm | good | OK | ✅ |
| `express` | npm | good | OK | ✅ |
| `lodash` | npm | good | OK | ✅ |
| `axios` | npm | good | OK | ✅ |
| `typescript` | npm | good | OK | ✅ |
| `reqeusts` | pypi | bad | DANGER | ✅ |
| `beautifulsoup-4` | pypi | bad | DANGER | ✅ |
| `djnago` | pypi | bad | DANGER | ✅ |
| `numpyy` | pypi | bad | DANGER | ✅ |
| `python-dateutils` | pypi | bad | DANGER | ✅ |
| `tensorlfow` | pypi | bad | DANGER | ✅ |
| `super-fast-http-client-helper-xyz` | pypi | bad | DANGER | ✅ |
| `auto-ml-easy-pipeline-2024` | pypi | bad | DANGER | ✅ |
| `zzz-nonexistent-pkg-001` | pypi | bad | DANGER | ✅ |
| `py-quick-json-validator-pro` | pypi | bad | DANGER | ✅ |
| `expresss` | npm | bad | WARN | ✅ |
| `loadsh` | npm | bad | WARN | ✅ |
| `reactt` | npm | bad | WARN | ✅ |
| `axioss` | npm | bad | WARN | ✅ |
| `super-cool-react-hooks-toolkit-xyz` | npm | bad | DANGER | ✅ |

## Methodology & honesty

- 30 hand-labeled entries in `benchmark/dataset.json` across PyPI and npm: 15 known-good popular packages (must end `OK`) and 15 bad names (nonexistent, AI-plausible hallucinations, and typosquats; must be flagged `WARN`/`DANGER`).
- A `bad` entry counts as detected if it is **not** `OK`. `UNKNOWN` results (rate-limited / offline) are excluded from the scores.
- Separately, 50 of the most popular real PyPI/npm packages were vetted with **0 false positives**.
- Reproduce: `python benchmark/run_benchmark.py` (needs network).
- This is a **curated** benchmark, not the full research corpus. Roadmap: extend with the [trendmicro/slopsquatting](https://github.com/trendmicro/slopsquatting) dataset.
