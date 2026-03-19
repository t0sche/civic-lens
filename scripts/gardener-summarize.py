#!/usr/bin/env python3
"""Summarize a gardener audit report for GitHub Actions step summary."""
import json
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: gardener-summarize.py <report.json>", file=sys.stderr)
        sys.exit(1)

    try:
        with open(sys.argv[1]) as f:
            r = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading report: {e}")
        sys.exit(1)

    print(r.get("summary", "No summary available."))
    print()

    s = r.get("stats", {})
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Total specs | {s.get('total_specs', '?')} |")
    print(f"| Implemented | {s.get('implemented_specs', '?')} |")
    print(f"| Partial | {s.get('partially_implemented', '?')} |")
    print(f"| Not started | {s.get('not_started', '?')} |")
    print(f"| Coverage | {s.get('coverage_pct', '?')}% |")
    print()

    for arrow in r.get("arrows", []):
        icon = "X" if arrow.get("drift_detected") else "OK"
        name = arrow.get("name", "unknown")
        declared = arrow.get("declared_status", "?")
        actual = arrow.get("actual_status", "?")
        print(f"- [{icon}] **{name}**: {declared} -> {actual}")
        for finding in arrow.get("findings", [])[:3]:
            severity = finding.get("severity", "?")
            detail = finding.get("detail", "")
            print(f"  - [{severity}] {detail}")

if __name__ == "__main__":
    main()
