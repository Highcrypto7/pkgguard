"""Measure pkgguard's detection rate against a labeled set (needs network).

Usage:
    python benchmark/run_benchmark.py            # human table
    python benchmark/run_benchmark.py --md       # markdown (for BENCHMARK.md)

'good' entries should resolve to OK; 'bad' entries (nonexistent / hallucinated /
typosquat) should be flagged (WARN or DANGER). UNKNOWN (couldn't check) is
reported separately and excluded from precision/recall so rate-limits don't
distort the numbers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pkgguard.engine import vet  # noqa: E402
from pkgguard.models import Grade  # noqa: E402

HERE = os.path.dirname(__file__)


def classify(grade: Grade) -> str:
    if grade is Grade.OK:
        return "pass"
    if grade in (Grade.WARN, Grade.DANGER):
        return "flag"
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true")
    args = ap.parse_args()

    data = json.load(open(os.path.join(HERE, "dataset.json"), encoding="utf-8"))
    entries = data["entries"]

    tp = fp = tn = fn = unknown = 0
    rows = []
    for e in entries:
        report = vet(e["name"], fmt="list", ecosystem=e["ecosystem"])
        ir = report.items[0] if report.items else None
        grade = ir.grade if ir else Grade.UNKNOWN
        result = classify(grade)
        label = e["label"]

        if result == "unknown":
            unknown += 1
            ok = None
        elif label == "bad":
            if result == "flag":
                tp += 1; ok = True
            else:
                fn += 1; ok = False
        else:  # good
            if result == "pass":
                tn += 1; ok = True
            else:
                fp += 1; ok = False
        rows.append((e["name"], e["ecosystem"], label, grade.label, ir.summary if ir else "", ok))

    total_scored = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    accuracy = (tp + tn) / total_scored if total_scored else 0.0

    if args.md:
        print("# pkgguard benchmark\n")
        print(f"- entries: {len(entries)}  (scored: {total_scored}, unknown/skipped: {unknown})")
        print(f"- **accuracy: {accuracy:.0%}**  ·  precision: {precision:.0%}  ·  recall: {recall:.0%}")
        print(f"- detected bad: {tp}/{tp+fn}  ·  false positives on good: {fp}/{tp+fp if False else tn+fp}\n")
        print("| name | eco | label | verdict | correct |")
        print("|---|---|---|---|---|")
        for name, eco, label, verdict, _summary, ok in rows:
            mark = "✅" if ok else ("❔" if ok is None else "❌")
            print(f"| `{name}` | {eco} | {label} | {verdict} | {mark} |")
    else:
        for name, eco, label, verdict, summary, ok in rows:
            mark = "OK " if ok else ("?? " if ok is None else "XX ")
            print(f"  {mark} [{label:4}] {name:38} -> {verdict:8} {summary}")
        print()
        print(f"scored={total_scored} unknown={unknown}  TP={tp} FN={fn} TN={tn} FP={fp}")
        print(f"accuracy={accuracy:.1%}  precision={precision:.1%}  recall={recall:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
