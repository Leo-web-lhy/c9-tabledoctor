"""Command line entry point. Console output is ASCII-only by design."""

import argparse
import os
import sys

from . import checks
from .loader import load_table
from .report import build_payload, load_i18n, write_html, write_json


def _a(text):
    """ASCII-safe rendering of any label for the console."""
    return str(text).encode("unicode_escape").decode("ascii")


def _default_out(src):
    base = os.path.splitext(os.path.basename(src))[0]
    folder = os.path.join(os.path.dirname(os.path.abspath(src)), "tabledoctor_out")
    return os.path.join(folder, base + ".report.html"), os.path.join(folder, base + ".report.json")


def build_parser():
    p = argparse.ArgumentParser(
        prog="tabledoctor",
        description="Local-first data hygiene checker for messy CSV/XLSX tables.",
    )
    sub = p.add_subparsers(dest="command")

    c = sub.add_parser("check", help="check one table and write a report")
    c.add_argument("path", help="path to .csv / .xlsx / .xlsm")
    c.add_argument("--out", default=None, help="output html path")
    c.add_argument("--json", dest="json_out", default=None, help="output json path")
    c.add_argument("--key", default=None, help="primary key column (name or 0-based index)")
    c.add_argument("--quiet", action="store_true", help="only print the summary line")

    v = sub.add_parser("checks", help="list every check rule")
    _ = v
    p.add_argument("--version", action="version", version="tabledoctor 0.1.0")
    return p


def _print_rules():
    i18n = load_i18n()
    for name in sorted(i18n["checks"]):
        meta = i18n["checks"][name]
        print("RULE %-22s %s" % (name, _a(meta["label"])))


def cmd_check(args):
    table = load_table(args.path)
    key_col = checks.resolve_key(table, args.key)
    if args.key is not None and key_col is None:
        print("[warn] key column not found: %s" % _a(args.key))
    issues = checks.run_all(table, key_col)

    default_html, default_json = _default_out(args.path)
    html_path = args.out or default_html
    json_path = args.json_out or default_json

    payload = build_payload(table, issues)
    write_json(payload, json_path)
    write_html(table, issues, html_path)

    if not args.quiet:
        for it in issues:
            col = it.get("column")
            label = ""
            if col is not None and col >= 0 and col < len(table["header"]):
                label = _a(table["header"][col])
            print("[issue] sev=%-7s check=%-20s col=%-3s label=%s count=%d" % (
                it["severity"], it["check"], col, label, it.get("count", 0)))
        for i, name in enumerate(table["header"]):
            print("[col] %d %s" % (i, _a(name)))

    counts = payload["counts"]
    print("[summary] file=%s rows=%d cols=%d enc=%s issues=%d error=%d warn=%d info=%d score=%d" % (
        _a(table["name"]), payload["rows"], payload["columns"], payload["encoding"],
        len(issues), counts["error"], counts["warning"], counts["info"], payload["score"]))
    print("[out] html=%s json=%s" % (_a(html_path), _a(json_path)))
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "checks":
        _print_rules()
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
