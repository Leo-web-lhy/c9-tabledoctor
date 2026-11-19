"""Deterministic data-quality checks. Every rule is pure and repeatable."""

import re

NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LOOSE_DATE_RE = re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$")
NULL_TOKENS = {"", "null", "none", "nan", "n/a", "na", "-", "--", "/", "?"}
INVISIBLE = ("\u3000", "\u200b", "\u00a0", "\ufeff")
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _s(v):
    return "" if v is None else str(v)


def is_blank(v):
    return _s(v).strip() == ""


def is_missing(v):
    return _s(v).strip().lower() in NULL_TOKENS


def _col(table, i):
    return [(_s(r[i]) if i < len(r) else "") for r in table["rows"]]


def _issue(check, severity, column, count, samples=None, message=""):
    return {
        "check": check,
        "severity": severity,
        "column": column,
        "count": count,
        "samples": (samples or [])[:5],
        "message": message,
    }


def check_ragged_rows(table):
    width = len(table["header"])
    bad = [i + 2 for i, r in enumerate(table["rows"]) if len(r) != width]
    if bad:
        return [_issue("ragged_rows", "error", -1, len(bad), bad, "row width != header width")]
    return []


def check_empty_columns(table):
    out = []
    for i in range(len(table["header"])):
        vals = _col(table, i)
        if vals and all(is_blank(v) for v in vals):
            out.append(_issue("empty_column", "error", i, len(vals), [], "all cells blank"))
    return out


def check_near_empty_columns(table):
    out = []
    total = len(table["rows"])
    if total < 20:
        return out
    for i in range(len(table["header"])):
        filled = sum(1 for v in _col(table, i) if not is_blank(v))
        if filled == 0:
            continue
        ratio = filled / float(total)
        if ratio <= 0.05:
            out.append(_issue("near_empty_column", "warning", i, total - filled, [],
                              "fill ratio %.3f" % ratio))
    return out


def check_high_missing(table):
    out = []
    total = len(table["rows"])
    if total == 0:
        return out
    for i in range(len(table["header"])):
        miss = sum(1 for v in _col(table, i) if is_missing(v))
        ratio = miss / float(total)
        if ratio > 0.9:
            continue
        if ratio > 0.5:
            out.append(_issue("high_missing_column", "warning", i, miss, [],
                              "missing ratio %.3f" % ratio))
    return out


def check_constant_columns(table):
    out = []
    if len(table["rows"]) < 5:
        return out
    for i in range(len(table["header"])):
        vals = [v for v in _col(table, i) if not is_blank(v)]
        if len(vals) < 5:
            continue
        distinct = set(vals)
        if len(distinct) == 1:
            out.append(_issue("constant_column", "info", i, len(vals), [vals[0]],
                              "single distinct value"))
    return out


def check_duplicate_rows(table):
    seen = {}
    dup = 0
    samples = []
    for idx, r in enumerate(table["rows"]):
        key = tuple(_s(c).strip() for c in r)
        if key in seen:
            dup += 1
            if len(samples) < 5:
                samples.append(idx + 2)
        else:
            seen[key] = idx
    if dup:
        return [_issue("duplicate_rows", "error", -1, dup, samples, "exact duplicate rows")]
    return []


def check_duplicate_key(table, key_col):
    if key_col is None:
        return []
    counts = {}
    for v in _col(table, key_col):
        k = v.strip()
        if k == "":
            continue
        counts[k] = counts.get(k, 0) + 1
    dup = sum(c - 1 for c in counts.values() if c > 1)
    if dup:
        samples = [k for k, c in counts.items() if c > 1][:5]
        return [_issue("duplicate_key", "error", key_col, dup, samples, "repeated key values")]
    return []


def check_type_mismatch(table):
    out = []
    for i in range(len(table["header"])):
        vals = [v.strip() for v in _col(table, i) if not is_blank(v)]
        if len(vals) < 5:
            continue
        num = sum(1 for v in vals if NUM_RE.match(v))
        r_num = num / float(len(vals))
        if r_num >= 0.9 and r_num < 1.0:
            bad = [v for v in vals if not NUM_RE.match(v)][:5]
            out.append(_issue("type_mismatch", "error", i, len(vals) - num, bad,
                              "numeric column with %d text cells" % (len(vals) - num)))
            continue
        date = sum(1 for v in vals if LOOSE_DATE_RE.match(v))
        iso = sum(1 for v in vals if ISO_DATE_RE.match(v))
        r_date = date / float(len(vals))
        r_iso = iso / float(len(vals))
        if r_date >= 0.9 and r_iso < 1.0:
            bad = [v for v in vals if not ISO_DATE_RE.match(v)][:5]
            out.append(_issue("type_mismatch", "error", i, len(vals) - iso, bad,
                              "date column mixing %d non-ISO values" % (len(vals) - iso)))
    return out


def check_whitespace(table):
    out = []
    for i in range(len(table["header"])):
        bad = []
        for v in _col(table, i):
            if v.strip() == "":
                continue
            if v != v.strip() or any(ch in v for ch in INVISIBLE):
                bad.append(v)
        if bad:
            out.append(_issue("whitespace_cells", "warning", i, len(bad),
                              ["repr:" + repr(b) for b in bad[:5]],
                              "leading/trailing/invisible whitespace"))
    return out


def resolve_key(table, key):
    """Accept a 0-based index or a header name. Returns index or None."""
    if key is None:
        return None
    if isinstance(key, int):
        return key if 0 <= key < len(table["header"]) else None
    text = str(key).strip()
    if text.isdigit():
        idx = int(text)
        return idx if 0 <= idx < len(table["header"]) else None
    for i, name in enumerate(table["header"]):
        if name == text:
            return i
    return None


def run_all(table, key_col=None):
    issues = []
    issues += check_ragged_rows(table)
    issues += check_empty_columns(table)
    issues += check_near_empty_columns(table)
    issues += check_high_missing(table)
    issues += check_constant_columns(table)
    issues += check_duplicate_rows(table)
    issues += check_duplicate_key(table, key_col)
    issues += check_type_mismatch(table)
    issues += check_whitespace(table)
    issues.sort(key=lambda x: (SEVERITY_ORDER.get(x["severity"], 3), x["check"], x["column"]))
    return issues
