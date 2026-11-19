"""Report writers: machine-readable JSON + a single-file HTML report (UTF-8)."""

import datetime
import html
import json
import os

I18N_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n.json")
PENALTY = {"error": 8, "warning": 4, "info": 1}


def load_i18n():
    with open(I18N_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def score_of(issues):
    score = 100
    for it in issues:
        score -= PENALTY.get(it["severity"], 2)
    return max(0, score)


def _summary(issues):
    return {
        "error": sum(1 for i in issues if i["severity"] == "error"),
        "warning": sum(1 for i in issues if i["severity"] == "warning"),
        "info": sum(1 for i in issues if i["severity"] == "info"),
    }


def build_payload(table, issues):
    return {
        "tool": "tabledoctor",
        "version": "0.1.0",
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file": table["name"],
        "path": table["source"],
        "rows": len(table["rows"]),
        "columns": len(table["header"]),
        "header": table["header"],
        "encoding": table["encoding"],
        "delimiter": table["delimiter"],
        "score": score_of(issues),
        "counts": _summary(issues),
        "issues": issues,
    }


def write_json(payload, out_path):
    folder = os.path.dirname(os.path.abspath(out_path))
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def _col_label(table, column):
    if column is None or column < 0:
        return None
    if 0 <= column < len(table["header"]):
        return "%s (#%d)" % (table["header"][column], column)
    return "#%d" % column


def _badge(severity, i18n):
    return '<span class="badge %s">%s</span>' % (
        severity, html.escape(i18n["severity"].get(severity, severity)))


def _rows_html(table, issues, i18n):
    if not issues:
        return '<tr><td colspan="6" class="empty">%s</td></tr>' % html.escape(i18n["no_issue"])
    out = []
    for it in issues:
        meta = i18n["checks"].get(it["check"], {"label": it["check"], "hint": ""})
        col = _col_label(table, it.get("column"))
        col = html.escape(col) if col else html.escape(i18n["column_whole_table"])
        samples = ", ".join(html.escape(str(s)) for s in it.get("samples") or [])
        note = meta["hint"]
        if it.get("message"):
            note = note + " | " + it["message"]
        out.append(
            "<tr>"
            "<td>%s</td>"
            "<td class=\"ck\">%s</td>"
            "<td>%s</td>"
            "<td class=\"num\">%d</td>"
            "<td class=\"samples\">%s</td>"
            "<td class=\"note\">%s</td>"
            "</tr>" % (
                _badge(it["severity"], i18n),
                html.escape(meta["label"]),
                col,
                it.get("count", 0),
                samples,
                html.escape(note),
            )
        )
    return "\n".join(out)


CSS = """
*{box-sizing:border-box}
body{margin:0;padding:32px;background:#f6f7f9;color:#1f2430;
 font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.6}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px}
.sub{color:#6b7280;font-size:13px;margin-bottom:24px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:24px}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px}
.card .k{font-size:12px;color:#6b7280;margin-bottom:6px}
.card .v{font-size:20px;font-weight:600;word-break:break-all}
.score .v{font-size:34px;color:%s}
table{width:100%%;border-collapse:collapse;background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;font-size:13px;vertical-align:top;border-bottom:1px solid #eef0f3}
th{background:#f9fafb;font-size:12px;color:#4b5563;font-weight:600}
tr:last-child td{border-bottom:none}
td.num{white-space:nowrap}
td.samples{color:#4b5563;font-family:ui-monospace,Consolas,monospace;font-size:12px}
td.note{color:#6b7280;font-size:12px}
td.ck{font-weight:600;white-space:nowrap}
td.empty{text-align:center;color:#059669;padding:28px}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;white-space:nowrap}
.badge.error{background:#fee2e2;color:#b91c1c}
.badge.warning{background:#fef3c7;color:#92400e}
.badge.info{background:#e0e7ff;color:#3730a3}
.foot{margin-top:20px;color:#9ca3af;font-size:12px}
"""


def write_html(table, issues, out_path, i18n=None):
    i18n = i18n or load_i18n()
    score = score_of(issues)
    tone = "#059669" if score >= 85 else ("#d97706" if score >= 60 else "#dc2626")
    counts = _summary(issues)
    payload_cols = "%d" % len(table["header"])
    enc = table["encoding"] or "-"
    if table["delimiter"]:
        enc = "%s / delim=%r" % (enc, table["delimiter"])
    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>%(title)s - %(file)s</title>
<style>%(css)s</style></head>
<body><div class="wrap">
<h1>%(title)s</h1>
<div class="sub">%(subtitle)s</div>
<div class="cards">
 <div class="card"><div class="k">%(label_file)s</div><div class="v">%(file)s</div></div>
 <div class="card"><div class="k">%(label_rows)s</div><div class="v">%(rows)s</div></div>
 <div class="card"><div class="k">%(label_cols)s</div><div class="v">%(cols)s</div></div>
 <div class="card"><div class="k">%(label_encoding)s</div><div class="v">%(enc)s</div></div>
 <div class="card score"><div class="k">%(label_score)s</div><div class="v">%(score)s</div></div>
 <div class="card"><div class="k">%(label_issues)s</div><div class="v">%(total)s</div></div>
</div>
<h2 style="font-size:16px;margin:0 0 10px">%(section_summary)s</h2>
<p style="font-size:13px;color:#4b5563;margin:0 0 24px">
&#38656;&#20462;&#22797; %(err)s &#183; &#24314;&#35758;&#22788;&#29702; %(warn)s &#183;
&#25552;&#31034; %(info)s</p>
<h2 style="font-size:16px;margin:0 0 10px">%(section_issues)s</h2>
<table>
<thead><tr>
<th>%(th_severity)s</th><th>%(th_check)s</th><th>%(th_column)s</th>
<th>%(th_count)s</th><th>%(th_samples)s</th><th>%(th_note)s</th>
</tr></thead>
<tbody>
%(body)s
</tbody></table>
<div class="foot">%(label_generated)s &#183; %(generated)s &#183; TableDoctor 0.1.0</div>
</div></body></html>
""" % {
        "title": html.escape(i18n["title"]),
        "subtitle": html.escape(i18n["subtitle"]),
        "css": CSS % tone,
        "label_file": html.escape(i18n["label_file"]),
        "file": html.escape(table["name"]),
        "label_rows": html.escape(i18n["label_rows"]),
        "rows": len(table["rows"]),
        "label_cols": html.escape(i18n["label_cols"]),
        "cols": payload_cols,
        "label_encoding": html.escape(i18n["label_encoding"]),
        "enc": html.escape(str(enc)),
        "label_score": html.escape(i18n["label_score"]),
        "score": score,
        "label_issues": html.escape(i18n["label_issues"]),
        "total": len(issues),
        "section_summary": html.escape(i18n["section_summary"]),
        "section_issues": html.escape(i18n["section_issues"]),
        "th_severity": html.escape(i18n["th_severity"]),
        "th_check": html.escape(i18n["th_check"]),
        "th_column": html.escape(i18n["th_column"]),
        "th_count": html.escape(i18n["th_count"]),
        "th_samples": html.escape(i18n["th_samples"]),
        "th_note": html.escape(i18n["th_note"]),
        "body": _rows_html(table, issues, i18n),
        "err": counts["error"],
        "warn": counts["warning"],
        "info": counts["info"],
        "label_generated": html.escape(i18n["label_generated"]),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    folder = os.path.dirname(os.path.abspath(out_path))
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return out_path
