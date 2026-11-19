"""Build fixture tables plus a ground-truth defect ledger.

Source is ASCII-only: Chinese labels live in fixture_spec.json and are read
at runtime. Output data files are written as UTF-8 where the format allows.
"""

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SPEC_PATH = os.path.join(HERE, "fixture_spec.json")
YEN = "\u5143"
CHANNEL = "\u5b98\u7f51"


def load_spec():
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_messy(spec):
    cols = spec["columns"]
    n = spec["row_count"]
    d = spec["defects"]
    rows = []
    for i in range(n):
        order = "SO2024%04d" % (i + 1)
        cust = spec["customers"][i % len(spec["customers"])]
        if i < d["whitespace_rows"]:
            cust = cust + " "
        day = "2024-03-%02d" % ((i % 28) + 1)
        region = spec["regions"][i % len(spec["regions"])]
        if i < d["region_missing_rows"]:
            region = ""
        amount = 100 + (i * 37) % 900
        note = ""
        starts = spec["note_start_rows"]
        if i in starts:
            note = spec["notes"][starts.index(i) % len(spec["notes"])]
        rows.append([order, cust, day, region, amount, note, "", CHANNEL])

    for j in range(d["loose_date_rows"]):
        idx = n - 1 - j
        rows[idx][2] = "2024/%d/%d" % ((idx % 12) + 1, (idx % 28) + 1)

    for j in range(d["text_amount_rows"]):
        idx = n - 2 - j
        rows[idx][4] = "1,200" + YEN

    for j in range(d["dup_key_rows"]):
        idx = 10 + j
        clone = list(rows[idx])
        clone[4] = clone[4] + 500
        rows.append(clone)

    for j in range(d["dup_row_copies"]):
        rows.append(list(rows[j]))
    return cols, rows


def build_clean(spec):
    n = spec["clean_row_count"]
    cols = spec["columns"][:5]
    rows = []
    for i in range(n):
        rows.append([
            "CLEAN%04d" % (i + 1),
            spec["customers"][i % len(spec["customers"])],
            "2024-05-%02d" % ((i % 28) + 1),
            spec["regions"][i % len(spec["regions"])],
            1000 + i * 13,
        ])
    return cols, rows


def write_xlsx(path, header, rows):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "data"
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)


def write_csv(path, header, rows, encoding, ragged=0):
    has_ragged = set()
    for k in range(ragged):
        has_ragged.add(len(rows) - 1 - k)
    with open(path, "w", encoding=encoding, newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i, r in enumerate(rows):
            if i in has_ragged:
                w.writerow(r[: max(1, len(header) - 3)])
            else:
                w.writerow(r)


def main():
    spec = load_spec()
    if not os.path.isdir(DATA):
        os.makedirs(DATA)

    cols, messy = build_messy(spec)
    clean_cols, clean_rows = build_clean(spec)
    ragged = spec["defects"]["ragged_csv_rows"]

    xlsx_path = os.path.join(DATA, "orders_messy.xlsx")
    csv_path = os.path.join(DATA, "orders_messy.csv")
    clean_path = os.path.join(DATA, "clean_orders.csv")

    write_xlsx(xlsx_path, cols, messy)
    write_csv(csv_path, cols, messy, "gb18030", ragged)
    write_csv(clean_path, clean_cols, clean_rows, "utf-8", 0)

    core = [
        {"check": "empty_column", "column": 6},
        {"check": "constant_column", "column": 7},
        {"check": "near_empty_column", "column": 5},
        {"check": "high_missing_column", "column": 3},
        {"check": "type_mismatch", "column": 4},
        {"check": "type_mismatch", "column": 2},
        {"check": "whitespace_cells", "column": 1},
        {"check": "duplicate_rows", "column": -1},
        {"check": "duplicate_key", "column": 0},
    ]
    truth = {
        "generated_by": "fixtures/gen.py",
        "seed": 20261119,
        "cases": [
            {
                "name": "orders_messy.xlsx",
                "path": os.path.join("data", "orders_messy.xlsx"),
                "key": 0,
                "rows": len(messy),
                "truth": core,
                "injected_defects": len(core),
            },
            {
                "name": "orders_messy.csv",
                "path": os.path.join("data", "orders_messy.csv"),
                "key": 0,
                "rows": len(messy),
                "truth": core + [{"check": "ragged_rows", "column": -1}],
                "injected_defects": len(core) + 1,
            },
            {
                "name": "clean_orders.csv",
                "path": os.path.join("data", "clean_orders.csv"),
                "key": 0,
                "rows": len(clean_rows),
                "truth": [],
                "injected_defects": 0,
            },
        ],
    }
    gt_path = os.path.join(DATA, "ground_truth.json")
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(truth, f, ensure_ascii=False, indent=2)

    print("FIXTURE xlsx=%s rows=%d cols=%d" % (os.path.basename(xlsx_path), len(messy), len(cols)))
    print("FIXTURE csv=%s rows=%d enc=gb18030 ragged=%d" % (os.path.basename(csv_path), len(messy), ragged))
    print("FIXTURE clean=%s rows=%d" % (os.path.basename(clean_path), len(clean_rows)))
    print("LEDGER cases=%d tokens=%d" % (len(truth["cases"]), sum(c["injected_defects"] for c in truth["cases"])))


if __name__ == "__main__":
    main()
