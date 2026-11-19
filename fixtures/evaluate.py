"""Score the checker against the injected-defect ledger (token-level recall)."""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tabledoctor import checks
from tabledoctor.loader import load_table

GT_PATH = os.path.join(HERE, "data", "ground_truth.json")
OUT_PATH = os.path.join(HERE, "eval_result.json")


def tokens(issues):
    return set((it["check"], it["column"]) for it in issues)


def fmt(tok):
    return "%s@col%s" % (tok[0], tok[1])


def run_case(case):
    path = os.path.join(HERE, case["path"])
    table = load_table(path)
    key_col = checks.resolve_key(table, case.get("key"))
    issues = checks.run_all(table, key_col)
    got = tokens(issues)
    truth = set((d["check"], d["column"]) for d in case["truth"])

    hit = got & truth
    missed = truth - got
    false_pos = got - truth
    recall = (len(hit) / float(len(truth))) if truth else 1.0
    precision = (len(hit) / float(len(got))) if got else (1.0 if not truth else 0.0)
    return {
        "name": case["name"],
        "rows": len(table["rows"]),
        "columns": len(table["header"]),
        "encoding": table["encoding"],
        "injected": len(truth),
        "detected": len(got),
        "matched": len(hit),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "missed": [fmt(t) for t in sorted(missed)],
        "false_positives": [fmt(t) for t in sorted(false_pos)],
        "issue_total": len(issues),
        "score": None,
    }


def main():
    with open(GT_PATH, "r", encoding="utf-8") as f:
        gt = json.load(f)
    results = [run_case(c) for c in gt["cases"]]

    total_inj = sum(r["injected"] for r in results)
    total_hit = sum(r["matched"] for r in results)
    total_fp = sum(len(r["false_positives"]) for r in results)
    overall_recall = (total_hit / float(total_inj)) if total_inj else 1.0
    overall_precision = (total_hit / float(total_hit + total_fp)) if (total_hit + total_fp) else 1.0

    for r in results:
        print("CASE %-20s rows=%-3d injected=%-2d detected=%-2d matched=%-2d recall=%.4f precision=%.4f" % (
            r["name"], r["rows"], r["injected"], r["detected"], r["matched"], r["recall"], r["precision"]))
        if r["missed"]:
            print("     MISSED %s" % ",".join(r["missed"]))
        if r["false_positives"]:
            print("     FALSE_POS %s" % ",".join(r["false_positives"]))

    print("OVERALL recall=%.4f precision=%.4f injected=%d matched=%d false_pos=%d" % (
        overall_recall, overall_precision, total_inj, total_hit, total_fp))

    payload = {
        "generated_by": "fixtures/evaluate.py",
        "overall": {
            "injected": total_inj,
            "matched": total_hit,
            "false_positives": total_fp,
            "recall": round(overall_recall, 4),
            "precision": round(overall_precision, 4),
        },
        "cases": results,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("OUT %s" % os.path.basename(OUT_PATH))
    return 0 if total_hit == total_inj and total_fp == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
