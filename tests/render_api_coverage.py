"""Render a route-level coverage document from the audit JSON."""
import argparse
from collections import defaultdict
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/api-coverage.md"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    s = report["summary"]
    lines = ["# API coverage audit", "", "Generated from the isolated test report; route hits are not branch coverage.", "", f"Tests: {s['tests_run']}; failures: {s['failures']}; errors: {s['errors']}; skipped: {s['skipped']}.", f"Method + route coverage: {s['covered_method_routes']}/{s['registered_method_routes']}; 2xx: {s['success_method_routes']}; redirects: {s.get('redirect_method_routes', 0)}; 4xx: {s['rejection_method_routes']}.", "", "Only requests belonging to passing tests count. A 401/403/404 alone is not successful business validation. HEAD/OPTIONS are excluded. Provider, mail, compute and Docker calls use mocks or loopback fixtures; real external end-to-end validation remains separate.", "", "## Modules", "", "| Module | Covered / total | 2xx | Redirect |", "| --- | --- | --- | --- |"]
    groups = defaultdict(list)
    for row in report["coverage"]:
        groups[row["module"].split(".")[-1]].append(row)
    for module, rows in sorted(groups.items()):
        lines.append(f"| {module} | {sum(bool(r['request_count']) for r in rows)} / {len(rows)} | {sum(r['success_exercised'] for r in rows)} | {sum(r.get('redirect_exercised',False) for r in rows)} |")
    lines += ["", "## Routes", "", "| Method | Route | Observed statuses | Passing tests |", "| --- | --- | --- | --- |"]
    for row in report["coverage"]:
        statuses = ", ".join(row["observed_statuses"]) or "UNCOVERED"
        names = "<br>".join(name.replace("|", "\\|") for name in row["passing_tests"])
        lines.append(f"| {row['method']} | `{row['rule']}` | {statuses} | {names} |")
    lines += ["", "## Skipped or failed tests", ""]
    issues = [(name, item) for name,item in report["tests"].items() if item["outcome"] != "passed"]
    lines += [f"- `{name}`: {item['outcome']} — {item.get('reason','')}" for name,item in issues] or ["None."]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text("\n".join(lines)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
