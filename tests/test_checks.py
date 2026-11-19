"""Assert-based unit tests for the check engine. Console output is ASCII-only."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tabledoctor import checks
from tabledoctor.report import score_of

PASSED = []
FAILED = []


def table(header, rows):
    return {"source": "mem", "name": "mem", "header": header, "rows": rows,
            "encoding": "mem", "delimiter": None}


def tokens(issues):
    return set((i["check"], i["column"]) for i in issues)


def case(name, fn):
    try:
        fn()
        PASSED.append(name)
    except AssertionError as exc:
        FAILED.append("%s: %s" % (name, exc))


def t_empty_column():
    t = table(["a", "b"], [["1", ""], ["2", ""], ["3", ""]])
    assert ("empty_column", 1) in tokens(checks.run_all(t)), "empty column missed"


def t_near_empty_column():
    rows = [["%d" % i, "x" if i == 0 else ""] for i in range(30)]
    t = table(["id", "note"], rows)
    assert ("near_empty_column", 1) in tokens(checks.run_all(t)), "near empty missed"


def t_near_empty_skipped_when_small():
    rows = [["%d" % i, "x" if i == 0 else ""] for i in range(10)]
    t = table(["id", "note"], rows)
    assert ("near_empty_column", 1) not in tokens(checks.run_all(t)), "rule fired below 20 rows"


def t_high_missing():
    rows = [["%d" % i, "" if i < 8 else "v%d" % i] for i in range(10)]
    t = table(["id", "col"], rows)
    assert ("high_missing_column", 1) in tokens(checks.run_all(t)), "high missing missed"


def t_constant_column():
    rows = [["%d" % i, "same"] for i in range(8)]
    t = table(["id", "ch"], rows)
    assert ("constant_column", 1) in tokens(checks.run_all(t)), "constant column missed"


def t_duplicate_rows():
    rows = [["1", "a"], ["2", "b"], ["1", "a"]]
    t = table(["id", "v"], rows)
    issues = [i for i in checks.run_all(t) if i["check"] == "duplicate_rows"]
    assert issues and issues[0]["count"] == 1, "duplicate row count wrong"


def t_duplicate_key():
    rows = [["1", "a"], ["1", "b"], ["2", "c"]]
    t = table(["id", "v"], rows)
    assert ("duplicate_key", 0) in tokens(checks.run_all(t, 0)), "duplicate key missed"


def t_type_mismatch_numeric():
    rows = [["%d" % i] for i in range(18)] + [["1,200"], ["n/a text"]]
    rows = [[r[0]] for r in rows]
    t = table(["amount"], rows)
    assert ("type_mismatch", 0) in tokens(checks.run_all(t)), "numeric mismatch missed"


def t_type_mismatch_date():
    rows = [["2024-01-%02d" % (i + 1)] for i in range(18)] + [["2024/1/9"], ["2024/2/3"]]
    t = table(["day"], rows)
    assert ("type_mismatch", 0) in tokens(checks.run_all(t)), "date mismatch missed"


def t_whitespace():
    rows = [[" a"], ["b "], ["c"]]
    t = table(["name"], rows)
    issues = [i for i in checks.run_all(t) if i["check"] == "whitespace_cells"]
    assert issues and issues[0]["count"] == 2, "whitespace count wrong"


def t_ragged_rows():
    rows = [["1", "a", "x"], ["2", "b"]]
    t = table(["id", "v", "w"], rows)
    assert ("ragged_rows", -1) in tokens(checks.run_all(t)), "ragged rows missed"


def t_clean_table_is_quiet():
    rows = [["%d" % i, "c%d" % (i % 3), "2024-06-%02d" % (i % 28 + 1), "%d" % (100 + i)]
            for i in range(25)]
    t = table(["id", "cust", "day", "amt"], rows)
    issues = checks.run_all(t, 0)
    assert not issues, "clean table produced %d issues" % len(issues)


def t_score_floor():
    rows = [["1"]] * 40
    t = table(["a"], rows)
    issues = checks.run_all(t)
    assert score_of(issues) >= 0, "score went negative"


def t_severity_order():
    rows = [[""], ["x"], ["x "]]
    t = table(["a"], rows)
    issues = checks.run_all(t)
    sev = [i["severity"] for i in issues]
    idx = {"error": 0, "warning": 1, "info": 2}
    assert all(idx[sev[i]] <= idx[sev[i + 1]] for i in range(len(sev) - 1)), "not severity sorted"


def main():
    cases = [
        ("empty_column", t_empty_column),
        ("near_empty_column", t_near_empty_column),
        ("near_empty_needs_20_rows", t_near_empty_skipped_when_small),
        ("high_missing", t_high_missing),
        ("constant_column", t_constant_column),
        ("duplicate_rows", t_duplicate_rows),
        ("duplicate_key", t_duplicate_key),
        ("type_mismatch_numeric", t_type_mismatch_numeric),
        ("type_mismatch_date", t_type_mismatch_date),
        ("whitespace", t_whitespace),
        ("ragged_rows", t_ragged_rows),
        ("clean_is_quiet", t_clean_table_is_quiet),
        ("score_floor", t_score_floor),
        ("severity_order", t_severity_order),
    ]
    for name, fn in cases:
        case(name, fn)
    for name in PASSED:
        print("PASS %s" % name)
    for item in FAILED:
        print("FAIL %s" % item)
    print("TOTAL passed=%d failed=%d" % (len(PASSED), len(FAILED)))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
