#!/usr/bin/env python3
"""
End-to-end validation test for resume templates.

Usage:
    python3 careerloop/rendering/test_validator.py
    python3 careerloop/rendering/test_validator.py --json
    python3 careerloop/rendering/test_validator.py --template all
    python3 careerloop/rendering/test_validator.py --template cv-template-v2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from careerloop.rendering.validator import ResumeValidator
from careerloop.rendering.normalizer import normalize


# ── Paths ──────────────────────────────────────────────────────────────────────

NICOBAR_RESUME = ROOT / "output/council/siddharth/nicobar-final/10_final_resume.md"
TEMPLATE_OUTPUT_DIR = ROOT / "output/resume_templates/siddharth/latest"

TEMPLATE_FILES = {
    "classic-ats": TEMPLATE_OUTPUT_DIR / "classic-ats.html",
    "compact-one-page": TEMPLATE_OUTPUT_DIR / "compact-one-page.html",
    "executive-clean": TEMPLATE_OUTPUT_DIR / "executive-clean.html",
    "founder-operator": TEMPLATE_OUTPUT_DIR / "founder-operator.html",
    "modern-accent": TEMPLATE_OUTPUT_DIR / "modern-accent.html",
    "product-engineer": TEMPLATE_OUTPUT_DIR / "product-engineer.html",
    "technical-two-column": TEMPLATE_OUTPUT_DIR / "technical-two-column.html",
    "cv-template-v2": TEMPLATE_OUTPUT_DIR / "cv-template-v2.html",
    "cv-template-v2-test": TEMPLATE_OUTPUT_DIR / "cv-template-v2-test.html",
}


# ── Main test runner ───────────────────────────────────────────────────────────

def run_validation(html_path: Path, template_name: str) -> dict:
    """Run the validator on a single template and return results dict."""
    if not html_path.exists():
        return {
            "template": template_name,
            "file": str(html_path),
            "status": "MISSING",
            "passed": False,
            "error_count": 0,
            "warning_count": 0,
            "rules": {},
        }

    html = html_path.read_text()
    v = ResumeValidator(html)
    passed, errors, warnings = v.validate()
    result = v.to_dict()

    result["template"] = template_name
    result["file"] = str(html_path)
    result["status"] = "PASS" if passed else "FAIL"

    return result


def run_all() -> list[dict]:
    """Validate all templates and return list of results."""
    return [
        run_validation(path, name)
        for name, path in sorted(TEMPLATE_FILES.items())
    ]


def run_markdown_audit(md_path: Path) -> dict:
    """Audit the source markdown for known issues (pre-render check)."""
    if not md_path.exists():
        return {"status": "MISSING", "issues": []}

    md_text = md_path.read_text()
    issues = []

    # Check for em dashes in body (exclude CSS/style blocks)
    body = md_text
    em_count = body.count("—")  # em dash
    en_count = body.count("–")  # en dash
    if em_count:
        issues.append(f"EM_DASH_IN_SOURCE: {em_count} em dashes found")
    if en_count:
        issues.append(f"EN_DASH_IN_SOURCE: {en_count} en dashes found (may be in date ranges)")

    # Check for arrows
    for arrow in ["→", "←", "↔"]:
        count = body.count(arrow)
        if count:
            name = {"→": "right", "←": "left", "↔": "both"}[arrow]
            issues.append(f"ARROW_IN_SOURCE: {count} {name} arrow(s) found")

    # Check for collapsed bullets in the raw markdown
    import re
    collapsed_pattern = re.compile(r"\s+[-–—]\s+(?=[A-Z])")
    collapsed_count = len(collapsed_pattern.findall(body))
    if collapsed_count > 10:  # threshold to flag
        issues.append(f"COLLAPSED_BULLETS_IN_SOURCE: {collapsed_count} potential collapsed bullet patterns found")

    # Check for forbidden terms
    forbidden_terms = [
        "Target Role", "Deal-breaker", "Internal Note",
        "Fit Score", "Council Verdict",
    ]
    for term in forbidden_terms:
        if term.lower() in body.lower():
            issues.append(f"FORBIDDEN_IN_SOURCE: '{term}' found")

    return {
        "status": "OK" if not issues else "ISSUES",
        "file": str(md_path),
        "issues": issues,
        "issue_count": len(issues),
    }


def normalize_and_report(md_path: Path) -> dict:
    """Normalize the resume and report statistics."""
    if not md_path.exists():
        return {"status": "MISSING"}

    md_text = md_path.read_text()
    resume = normalize(md_text)

    return {
        "status": "OK",
        "name": resume.header.name,
        "email": resume.header.email,
        "has_phone": bool(resume.header.phone),
        "has_location": bool(resume.header.location),
        "has_portfolio": bool(resume.header.portfolio_url),
        "has_github": bool(resume.header.github_url),
        "profile_length": len(resume.profile),
        "skill_count": len(resume.skills),
        "experience_count": len(resume.experience),
        "total_bullets": sum(len(e.bullets) for e in resume.experience),
        "bullet_distribution": {
            f"{e.role} @ {e.company}": len(e.bullets)
            for e in resume.experience
        },
        "achievement_count": len(resume.achievements),
        "education_count": len(resume.education),
        "has_thesis": resume.thesis is not None,
        "language_count": len(resume.languages),
        "single_blob_entries": sum(
            1 for e in resume.experience if len(e.bullets) == 1
        ),
        "max_bullets_per_role": max(
            (len(e.bullets) for e in resume.experience), default=0
        ),
    }


# ── Output formatters ──────────────────────────────────────────────────────────

def print_table(results: list[dict]) -> None:
    """Print a formatted table of validation results."""
    header = f"{'Template':<24} {'Status':<8} {'Errors':>7} {'Warnings':>9}"
    sep = "-" * len(header)

    print()
    print(sep)
    print("Resume Template Validation Results")
    print(sep)
    print(header)
    print(sep)

    for r in results:
        status = r["status"]
        errors = r.get("error_count", 0)
        warnings = r.get("warning_count", 0)
        print(
            f"{r['template']:<24} {status:<8} {errors:>7} {warnings:>9}"
        )

    print(sep)
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len([r for r in results if r["status"] != "MISSING"])
    print(f"Passed: {passed}/{total}")


def print_rule_details(results: list[dict], template_name: str = None) -> None:
    """Print per-rule details for each template."""
    for r in results:
        if template_name and r["template"] != template_name:
            continue
        if r["status"] == "MISSING":
            print(f"\n{r['template']}: FILE NOT FOUND")
            continue

        print(f"\n{'='*60}")
        print(f"  {r['template']}  [{r['status']}]")
        print(f"  File: {r['file']}")
        print(f"  Errors: {r.get('error_count', 0)}, Warnings: {r.get('warning_count', 0)}")
        print(f"{'='*60}")

        rules = r.get("rules", {})
        if not rules:
            print("  (no rule results)")
            continue

        for rule_id, rule_data in sorted(rules.items()):
            icon = "PASS" if rule_data["passed"] else "FAIL"
            sev = rule_data["severity"]
            print(f"  [{icon}] {rule_id} ({sev})")
            if rule_data.get("details"):
                print(f"        {rule_data['details']}")


def print_markdown_audit(audit: dict) -> None:
    """Print source markdown audit results."""
    print(f"\n{'='*60}")
    print("Source Markdown Audit")
    print(f"{'='*60}")
    print(f"  File: {audit.get('file', 'N/A')}")
    print(f"  Status: {audit['status']}")
    if audit.get("issues"):
        for issue in audit["issues"]:
            print(f"  [!] {issue}")
    else:
        print("  No issues found in source markdown.")


def print_normalizer_report(report: dict) -> None:
    """Print normalizer statistics."""
    print(f"\n{'='*60}")
    print("Normalizer Statistics")
    print(f"{'='*60}")
    if report["status"] == "MISSING":
        print("  Source file not found.")
        return

    print(f"  Name:          {report['name']}")
    print(f"  Email:         {report['email']}")
    print(f"  Phone:         {'Yes' if report['has_phone'] else 'No'}")
    print(f"  Location:      {'Yes' if report['has_location'] else 'No'}")
    print(f"  Portfolio:     {'Yes' if report['has_portfolio'] else 'No'}")
    print(f"  GitHub:        {'Yes' if report['has_github'] else 'No'}")
    print(f"  Profile:       {report['profile_length']} chars")
    print(f"  Skills:        {report['skill_count']} rows")
    print(f"  Experience:    {report['experience_count']} entries, {report['total_bullets']} total bullets")
    print(f"  Achievements:  {report['achievement_count']}")
    print(f"  Education:     {report['education_count']} entries")
    print(f"  Thesis:        {'Yes' if report['has_thesis'] else 'No'}")
    print(f"  Languages:     {report['language_count']}")

    if report.get("single_blob_entries"):
        print(f"\n  WARNING: {report['single_blob_entries']} experience entries have only 1 bullet!")
    print(f"  Max bullets:   {report['max_bullets_per_role']} per role")

    if report.get("bullet_distribution"):
        print("\n  Bullet distribution:")
        for role, count in report["bullet_distribution"].items():
            print(f"    [{count}] {role}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="End-to-end validation test for resume templates"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--template", type=str, default="all",
        help="Validate specific template (e.g., cv-template-v2) or 'all'",
    )
    parser.add_argument(
        "--audit-source", action="store_true",
        help="Also audit the source markdown",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Run full validation: source audit + normalize + all templates + rule details",
    )
    args = parser.parse_args()

    results = []

    # 1. Source markdown audit
    if args.full or args.audit_source:
        audit = run_markdown_audit(NICOBAR_RESUME)
        if args.json:
            results.append({"type": "source_audit", **audit})
        else:
            print_markdown_audit(audit)

    # 2. Normalizer statistics
    if args.full:
        norm_report = normalize_and_report(NICOBAR_RESUME)
        if args.json:
            results.append({"type": "normalizer", **norm_report})
        else:
            print_normalizer_report(norm_report)

    # 3. Template validation
    if args.template == "all":
        template_results = run_all()
    else:
        if args.template not in TEMPLATE_FILES:
            print(f"Unknown template: {args.template}")
            print(f"Available: {', '.join(sorted(TEMPLATE_FILES.keys()))}")
            sys.exit(1)
        path = TEMPLATE_FILES[args.template]
        template_results = [run_validation(path, args.template)]

    if args.json:
        results.extend({"type": "template_validation", **r} for r in template_results)
        print(json.dumps(results, indent=2))
    else:
        if args.full:
            print_rule_details(template_results)
        else:
            print_table(template_results)

    # Exit code
    all_passed = all(
        r["status"] in ("PASS", "MISSING")
        for r in template_results
    )
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
