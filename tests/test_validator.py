#!/usr/bin/env python3
"""
test_validator.py — Quick validation test for fill-template.py output.

1. Runs fill-template.py on the Nicobar resume to generate v2 HTML
2. Validates the output with ResumeValidator
3. Prints pass/fail for each rule
4. Exits 0 if all ERROR rules pass, 1 if any fail
"""

import subprocess
import sys
from pathlib import Path

# Paths
RESUME_MD = "output/council/siddharth/nicobar-final/10_final_resume.md"
TEMPLATE_HTML = "templates/cv-template-v2.html"
OUTPUT_HTML = "output/resume_templates/siddharth/latest/cv-template-v2-test.html"


def run_fill_template():
    """Run fill-template.py to generate HTML."""
    print("=" * 60)
    print("Step 1: Generate HTML from Nicobar resume")
    print(f"  Source: {RESUME_MD}")
    print(f"  Template: {TEMPLATE_HTML}")
    print(f"  Output: {OUTPUT_HTML}")

    result = subprocess.run(
        ["python3", "fill-template.py", RESUME_MD, TEMPLATE_HTML, OUTPUT_HTML],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"FATAL: fill-template.py failed")
        print(result.stderr)
        sys.exit(2)

    print(result.stdout.strip())
    print()
    return True


def run_validator():
    """Run ResumeValidator on the generated HTML."""
    from careerloop.rendering.validator import ResumeValidator

    html_path = Path(OUTPUT_HTML)
    if not html_path.exists():
        print(f"FATAL: Output HTML not found: {OUTPUT_HTML}")
        sys.exit(3)

    print("=" * 60)
    print("Step 2: Validate HTML with ResumeValidator")
    print(f"  File: {OUTPUT_HTML} ({html_path.stat().st_size} bytes)")

    html = html_path.read_text()
    v = ResumeValidator(html)
    passed, errors, warnings = v.validate()

    print()
    print("Rule Results:")
    print("-" * 40)
    all_pass = True
    for r in v._report.results:
        icon = r.icon()
        status = "PASS" if r.passed else "FAIL"
        line = f"  {icon} {r.rule_id} [{r.severity}] — {status}"
        print(line)
        if not r.passed and r.details:
            print(f"       {r.details}")
        if r.severity == "ERROR" and not r.passed:
            all_pass = False

    print()
    print("-" * 40)
    print(f"Total Errors:   {v._report.error_count}")
    print(f"Total Warnings: {v._report.warning_count}")
    print(f"Overall:        {'PASS' if all_pass else 'FAIL'}")

    # Also generate a quick summary of what's in the output
    print()
    print("Content Summary:")
    print(f"  Name:        {_extract_text(html, '<h1>', '</h1>')}")
    print(f"  <li> count:  {html.count('<li>')}")
    print(f"  <ul> count:  {html.count('<ul>')}")
    print(f"  h2 sections: {html.count('<h2>')}")

    return all_pass


def _extract_text(html: str, start_tag: str, end_tag: str) -> str:
    """Extract text between tags."""
    import re
    m = re.search(re.escape(start_tag) + r"(.*?)" + re.escape(end_tag), html)
    return m.group(1).strip() if m else "N/A"


def main():
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║  CareerLoop Resume Validator — Integration Test ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    run_fill_template()
    all_pass = run_validator()

    print()
    if all_pass:
        print("RESULT: All ERROR rules PASSED")
    else:
        print("RESULT: Some ERROR rules FAILED — check details above")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
