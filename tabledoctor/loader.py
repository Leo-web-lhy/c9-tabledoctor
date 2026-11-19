"""Table loading for TableDoctor (CSV / XLSX) - standard library + openpyxl only."""

import csv
import datetime
import os

CSV_ENCODINGS = ["utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "latin-1"]
DELIMS = [",", "\t", ";", "|"]


def is_blank(v):
    """Strictly blank: None or whitespace-only string."""
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    return False


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, datetime.date):
        return v.strftime("%Y-%m-%d")
    return v


def _guess_delim(sample):
    best, best_n = ",", -1
    for d in DELIMS:
        n = sample.count(d)
        if n > best_n:
            best, best_n = d, n
    return best


def load_csv(path):
    last_err = None
    for enc in CSV_ENCODINGS:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                sample = f.read(65536)
                f.seek(0)
                delim = _guess_delim(sample)
                rows = [[_cell(c) for c in r] for r in csv.reader(f, delimiter=delim)]
            if not rows:
                raise ValueError("empty csv")
            return _table(rows, path, enc, delim)
        except UnicodeDecodeError as exc:
            last_err = exc
            continue
    raise RuntimeError("cannot decode csv %s: %s" % (path, last_err))


def load_xlsx(path):
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append([_cell(c) for c in row])
    wb.close()
    while rows and all(is_blank(c) for c in rows[-1]):
        rows.pop()
    if not rows:
        raise ValueError("empty sheet")
    return _table(rows, path, "xlsx", None)


def _table(rows, path, enc, delim):
    header = []
    for i, c in enumerate(rows[0]):
        text = str(c).strip() if not is_blank(c) else ""
        header.append(text if text else "col_%d" % i)
    return {
        "source": os.path.abspath(path),
        "name": os.path.basename(path),
        "header": header,
        "rows": rows[1:],
        "encoding": enc,
        "delimiter": delim,
    }


def load_table(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        return load_xlsx(path)
    return load_csv(path)
