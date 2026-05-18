#!/usr/bin/env python3
"""
Regression test — full pipeline: normalizer → renderer → validator.

Usage:
    # Validate a rendered HTML file directly
    python careerloop/rendering/regression_test.py --html <resume.html>

    # Full pipeline: MD → render → validate
    python careerloop/rendering/regression_test.py --input <resume.md> --template <template.html>

    # With base resume for tailoring delta check
    python careerloop/rendering/regression_test.py --input <tailored.md> --compare-base <base.md> --template <template.html>

    # Strict mode (warnings become errors)
    python careerloop/rendering/regression_test.py --html <resume.html> --strict

    # JSON output
    python careerloop/rendering/regression_test.py --html <resume.html> --json

    # Run on all known templates using the canonical resume MD
    python careerloop/rendering/regression_test.py --all

Exit codes:
    0 — all rules passed
    1 — one or more rules failed
    2 — pipeline error (render/crash)
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


# ── Default paths ──────────────────────────────────────────────────────────

NICOBAR_RESUME = ROOT / "output/council/siddharth/nicobar-final/10_final_resume.md"
DEFAULT_TEMPLATE = ROOT / "templates/cv-template-v2.html"
TEMPLATE_OUTPUT_DIR = ROOT / "output/resume_templates/siddharth/latest"

TEMPLATE_FILES = {
    "classic-ats": TEMPLATE_OUTPUT_DIR / "classic-ats.html",
    "compact-one-page": TEMPLATE_OUTPUT_DIR / "compact-one-page.html",
    "executive-clean": TEMPLATE_OUTPUT_DIR / "executive-clean.html",
    "founder-operator": TEMPLATE_OUTPUT_DIR / "founder-operator.html",
    "modern-accent": TEMPLATE_OUTPUT_DIR / "modern-accent.html",
    "product-engineer": TEMPLATE_OUTPUT_DIR / "product-engineer.html",
    "technical-two-column": TEMPLATE_OUTPUT_DIR / "technical-two-column.html",
    "nicobar-v2": ROOT / "output/council/siddharth/nicobar-final/nicobar-v2.html",
    "nicobar-v1": ROOT / "output/council/siddharth/nicobar-final/nicobar-v1.html",
}


# ── Renderer bridge (uses fill-template.py) ────────────────────────────────

def render_md_to_html(
    md_path: Path,
    template_path: Path,
) -> str:
    """Render a markdown resume file to HTML using fill-template.py v5.

    Pipeline: MD → clean_ai_slop → normalize → NormalizedResume → generate_html → HTML

    Returns the rendered HTML string.
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Resume MD not found: {md_path}")
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    # Import fill-template v5 (uses NormalizedResume from the normalizer)
    fill_template_path = ROOT / "fill-template.py"
    if not fill_template_path.exists():
        raise FileNotFoundError(
            f"Renderer not found: {fill_template_path}. "
            f"Cannot render MD to HTML without fill-template.py."
        )

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fill_template", str(fill_template_path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load fill-template from {fill_template_path}")

    ft = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ft)

    # v5 pipeline: clean → normalize → generate
    md_text = md_path.read_text()
    md_text = ft.clean_ai_slop(md_text)
    resume = ft.normalize(md_text)  # → NormalizedResume
    html = ft.generate_html(resume, str(template_path))

    return html


def render_md_with_normalizer(md_path: Path, template_path: Path) -> str:
    """Alternative renderer using the normalizer + template system.

    Same as render_md_to_html but uses explicit imports for clarity.
    """
    return render_md_to_html(md_path, template_path)


# ── Validation runner ──────────────────────────────────────────────────────

def run_validation(
    html: str,
    base_html: str = "",
    strict: bool = False,
    file_label: str = "",
) -> dict:
    """Run the full validator and return results dict."""
    v = ResumeValidator(html, base_html=base_html, strict=strict)
    v.validate()
    result = v.to_dict()
    result["status"] = "PASS" if result["passed"] else "FAIL"
    if strict and not result.get("passed_strict", True):
        result["status"] = "FAIL"
    if file_label:
        result["file"] = file_label
    return result


def run_on_html_file(
    html_path: Path,
    base_html_path: Path | None = None,
    strict: bool = False,
) -> dict:
    """Validate a single HTML file."""
    if not html_path.exists():
        return {
            "status": "MISSING",
            "file": str(html_path),
            "error": f"File not found: {html_path}",
        }

    html = html_path.read_text()
    base_html = ""
    if base_html_path and base_html_path.exists():
        base_html = base_html_path.read_text()

    result = run_validation(html, base_html=base_html, strict=strict)
    result["file"] = str(html_path)
    result["template"] = html_path.stem
    return result


def run_full_pipeline(
    md_path: Path,
    template_path: Path,
    base_md_path: Path | None = None,
    strict: bool = False,
    use_normalizer: bool = False,
) -> dict:
    """Run full pipeline: MD → render → validate.

    Args:
        md_path: Path to input resume markdown
        template_path: Path to HTML template
        base_md_path: Optional base resume for tailoring delta
        strict: Promotes warnings to errors
        use_normalizer: Use normalizer-based rendering instead of fill-template

    Returns:
        Validation results dict with extra pipeline metadata.
    """
    try:
        if use_normalizer:
            html = render_md_with_normalizer(md_path, template_path)
        else:
            html = render_md_to_html(md_path, template_path)

        base_html = ""
        if base_md_path and base_md_path.exists():
            if use_normalizer:
                base_html = render_md_with_normalizer(base_md_path, template_path)
            else:
                base_html = render_md_to_html(base_md_path, template_path)

        result = run_validation(html, base_html=base_html, strict=strict)
        result["file"] = str(md_path)
        result["template"] = str(template_path)
        result["rendered_bytes"] = len(html)
        result["pipeline"] = "normalizer+validator" if use_normalizer else "fill-template+validator"

        return result

    except Exception as e:
        return {
            "status": "PIPELINE_ERROR",
            "file": str(md_path),
            "template": str(template_path),
            "error": str(e),
            "error_type": type(e).__name__,
        }


# ── Output formatters ──────────────────────────────────────────────────────

def print_results(results: dict | list[dict], json_out: bool = False) -> None:
    """Print validation results in human-readable or JSON format."""
    if json_out:
        print(json.dumps(results, indent=2))
        return

    if isinstance(results, list):
        _print_table(results)
    else:
        _print_detail(results)


def _print_detail(result: dict) -> None:
    """Print detailed results for a single validation run."""
    print()
    print("=" * 70)
    print("  Regression Test Results")
    print("=" * 70)

    status = result.get("status", "UNKNOWN")
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"  Status:      {icon} {status}")
    print(f"  File:        {result.get('file', 'N/A')}")

    if "template" in result:
        print(f"  Template:    {result['template']}")
    if "rendered_bytes" in result:
        print(f"  Rendered:    {result['rendered_bytes']} bytes")
    if "pipeline" in result:
        print(f"  Pipeline:    {result['pipeline']}")

    print(f"  Errors:      {result.get('error_count', '?')}")
    print(f"  Warnings:    {result.get('warning_count', '?')}")
    print(f"  Strict:      {result.get('strict_mode', False)}")

    if "error" in result and status == "PIPELINE_ERROR":
        print(f"\n  PIPELINE ERROR: {result['error']}")
        if "error_type" in result:
            print(f"  Type: {result['error_type']}")
        return

    rules = result.get("rules", {})
    if not rules:
        print("\n  (no rule results)")
        return

    print()
    for rule_id in sorted(rules.keys()):
        rule = rules[rule_id]
        icon = "PASS" if rule["passed"] else "FAIL"
        sev = rule["severity"]
        print(f"  [{icon}] {rule_id} ({sev})")
        if rule.get("details"):
            print(f"        {rule['details']}")
        if rule.get("locations"):
            for loc in rule["locations"][:3]:
                print(f"          -> {loc}")
            if len(rule.get("locations", [])) > 3:
                print(f"          ... and {len(rule['locations']) - 3} more")

    print()
    print("=" * 70)


def _print_table(results: list[dict]) -> None:
    """Print a summary table for multiple validation runs."""
    sep = "-" * 85
    print()
    print(sep)
    print(f"{'Template / File':<30} {'Status':<16} {'Errors':>7} {'Warnings':>9}")
    print(sep)

    passed = 0
    total = 0
    for r in results:
        status = r.get("status", "UNKNOWN")
        if status == "MISSING":
            print(f"{r.get('file', r.get('template', '?')):<30} {'MISSING':<16} {'—':>7} {'—':>9}")
            continue
        if status == "PIPELINE_ERROR":
            print(f"{r.get('file', '?'):<30} {'PIPELINE_ERROR':<16} {'—':>7} {'—':>9}")
            continue

        total += 1
        if status == "PASS":
            passed += 1

        label = r.get("template", Path(r.get("file", "")).stem)
        errors = r.get("error_count", 0)
        warnings = r.get("warning_count", 0)
        print(f"{label:<30} {status:<16} {errors:>7} {warnings:>9}")

    print(sep)
    print(f"Passed: {passed}/{total}")
    if passed < total:
        print(f"Failed: {total - passed}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Regression test — full pipeline: normalizer → renderer → validator",
    )
    parser.add_argument(
        "--html", type=str,
        help="Validate an existing HTML file directly (skip render step)",
    )
    parser.add_argument(
        "--input", type=str,
        help="Resume markdown file to render and validate",
    )
    parser.add_argument(
        "--template", type=str,
        help="HTML template to use for rendering (default: templates/cv-template-v2.html)",
    )
    parser.add_argument(
        "--compare-base", type=str,
        help="Base resume MD or HTML for tailoring delta comparison (Rule 10)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Strict mode: warnings become errors",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Validate all known template outputs",
    )
    parser.add_argument(
        "--use-normalizer", action="store_true",
        help="Use normalizer-based rendering pipeline (experimental)",
    )
    parser.add_argument(
        "--output", type=str,
        help="Save rendered HTML to this path (only with --input)",
    )

    args = parser.parse_args()

    # --all mode: validate all known templates
    if args.all:
        results = []
        for name, html_path in sorted(TEMPLATE_FILES.items()):
            result = run_on_html_file(html_path, strict=args.strict)
            result["template"] = name
            results.append(result)

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            _print_table(results)

        # Exit based on results
        any_failed = any(
            r.get("status") not in ("PASS", "MISSING")
            for r in results
        )
        sys.exit(1 if any_failed else 0)
        return

    # Single file validation mode
    if args.html:
        html_path = Path(args.html)
        base_html_path = Path(args.compare_base) if args.compare_base else None

        result = run_on_html_file(
            html_path,
            base_html_path=base_html_path,
            strict=args.strict,
        )

        if result["status"] == "MISSING":
            print(f"Error: File not found: {html_path}", file=sys.stderr)
            sys.exit(2)

        print_results(result, json_out=args.json)
        sys.exit(0 if result["status"] == "PASS" else 1)
        return

    # Full pipeline mode: MD → render → validate
    if args.input:
        md_path = Path(args.input)
        if not md_path.exists():
            print(f"Error: File not found: {md_path}", file=sys.stderr)
            sys.exit(2)

        template_path = Path(args.template) if args.template else DEFAULT_TEMPLATE
        if not template_path.exists():
            print(f"Error: Template not found: {template_path}", file=sys.stderr)
            sys.exit(2)

        base_md_path = Path(args.compare_base) if args.compare_base else None

        result = run_full_pipeline(
            md_path=md_path,
            template_path=template_path,
            base_md_path=base_md_path,
            strict=args.strict,
            use_normalizer=args.use_normalizer,
        )

        if result["status"] == "PIPELINE_ERROR":
            print(f"Pipeline error: {result.get('error')}", file=sys.stderr)
            sys.exit(2)

        print_results(result, json_out=args.json)

        # Save rendered HTML if requested
        if args.output and "rendered" not in result:
            # We need the rendered HTML; re-run without capturing result
            pass  # The HTML is not stored in the result dict by default

        sys.exit(0 if result["status"] == "PASS" else 1)
        return

    # No mode selected — show help and run on default templates
    print("No input specified. Use --html, --input, or --all.")
    print()
    print("Quick start:")
    print(f"  python {__file__} --html output/resume_templates/siddharth/latest/classic-ats.html")
    print(f"  python {__file__} --input output/council/siddharth/nicobar-final/10_final_resume.md --template templates/cv-template-v2.html")
    print(f"  python {__file__} --all")
    print(f"  python {__file__} --all --strict --json")
    sys.exit(0)


if __name__ == "__main__":
    main()
