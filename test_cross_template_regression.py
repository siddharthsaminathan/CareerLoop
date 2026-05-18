#!/usr/bin/env python3
"""
Cross-Template Regression Tester
Renders ALL templates against multiple resumes and produces a QA report.
"""

import subprocess
import sys
import os
import json
import re
import difflib
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path("/Users/siddharthsaminathan/Projects/CareerLoop")
os.chdir(PROJECT_ROOT)

# ── Test configurations ─────────────────────────────────────────────────
TEST_SUITES = [
    {
        "id": "siddharth-nicobar",
        "name": "Siddharth (Nicobar-tailored)",
        "resume_path": str(PROJECT_ROOT / "output/council/siddharth/nicobar-final/10_final_resume.md"),
        "candidate": "siddharth",
        "run_id": "nicobar-regression",
    },
    {
        "id": "siddharth-base",
        "name": "Siddharth (Base cv.md)",
        "resume_path": str(PROJECT_ROOT / "cv.md"),
        "candidate": "siddharth",
        "run_id": "base-regression",
    },
    {
        "id": "alex-experienced",
        "name": "Alex Chen (Experienced Tech)",
        "resume_path": str(PROJECT_ROOT / "examples/fixtures/experienced_tech.md"),
        "candidate": "alex",
        "run_id": "regression",
    },
    {
        "id": "priya-fresher",
        "name": "Priya Sharma (Fresher ML)",
        "resume_path": str(PROJECT_ROOT / "examples/fixtures/fresher_ml.md"),
        "candidate": "priya",
        "run_id": "regression",
    },
]

TEMPLATE_REGISTRY = {
    "classic-ats": "classic_ats.html",
    "modern-accent": "modern_accent.html",
    "executive-clean": "executive_clean.html",
    "compact-one-page": "compact_one_page.html",
    "technical-two-column": "technical_two_column.html",
    "product-engineer": "product_engineer.html",
    "founder-operator": "founder_operator.html",
}

# ── Output directories ──────────────────────────────────────────────────
V2_OUTPUT_DIR = PROJECT_ROOT / "output/regression_test"
V2_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helper functions ────────────────────────────────────────────────────
def run_cmd(cmd, timeout=120):
    """Run a command and return (success, stdout, stderr, returncode)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return False, "", f"TIMEOUT after {timeout}s", -1
    except Exception as e:
        return False, "", str(e), -1

def render_v2_v1(suite):
    """Render v2 and v1 using fill-template.py."""
    resume_path = suite["resume_path"]
    out_dir = V2_OUTPUT_DIR / suite["id"]
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # V2 template
    v2_out = out_dir / "v2.html"
    cmd = [
        "python3", "-c", f"""
import sys
sys.path.insert(0, '{PROJECT_ROOT}')
sys.path.insert(0, '{PROJECT_ROOT}/careerloop')
os.chdir('{PROJECT_ROOT}')
exec(open('fill-template.py').read())
""",
        resume_path,
        str(PROJECT_ROOT / "templates/cv-template-v2.html"),
        str(v2_out)
    ]
    ok, stdout, stderr, rc = run_cmd(cmd)
    results["v2"] = {"ok": ok, "path": str(v2_out), "stdout": stdout, "stderr": stderr}

    # V1 template
    v1_out = out_dir / "v1.html"
    ok, stdout, stderr, rc = run_cmd([
        "python3", "-c", f"""
import sys, os
sys.path.insert(0, '{PROJECT_ROOT}')
sys.path.insert(0, '{PROJECT_ROOT}/careerloop')
os.chdir('{PROJECT_ROOT}')
exec(open('fill-template.py').read())
""",
        resume_path,
        str(PROJECT_ROOT / "templates/cv-template.html"),
        str(v1_out)
    ])
    results["v1"] = {"ok": ok, "path": str(v1_out), "stdout": stdout, "stderr": stderr}

    return results

def render_gemini_templates(suite):
    """Render all 7 Gemini templates using render_all_templates.py."""
    out_dir_base = PROJECT_ROOT / f"output/resume_templates/{suite['candidate']}/{suite['run_id']}"
    out_dir_base.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3", "-c", f"""
import sys, os
sys.path.insert(0, '{PROJECT_ROOT}')
sys.path.insert(0, '{PROJECT_ROOT}/careerloop')
os.chdir('{PROJECT_ROOT}')
exec(open('careerloop/rendering/render_all_templates.py').read())
""",
        "--input", suite["resume_path"],
        "--candidate", suite["candidate"],
        "--run-id", suite["run_id"],
    ]
    ok, stdout, stderr, rc = run_cmd(cmd, timeout=180)
    results = {
        "ok": ok,
        "stdout": stdout,
        "stderr": stderr,
        "out_dir": str(out_dir_base),
        "templates": {}
    }

    # Collect generated HTML files
    for tmpl_id in TEMPLATE_REGISTRY:
        html_path = out_dir_base / f"{tmpl_id}.html"
        pdf_path = out_dir_base / f"{tmpl_id}.pdf"
        results["templates"][tmpl_id] = {
            "html_exists": html_path.exists(),
            "html_path": str(html_path) if html_path.exists() else None,
            "pdf_exists": pdf_path.exists(),
            "pdf_path": str(pdf_path) if pdf_path.exists() else None,
        }
    return results

def validate_html(html_path):
    """Run ResumeValidator on a single HTML file."""
    if not html_path or not Path(html_path).exists():
        return {"error": f"File not found: {html_path}"}

    from careerloop.rendering.validator import ResumeValidator
    html = Path(html_path).read_text()
    v = ResumeValidator(html)
    passed, errors, warnings = v.validate()
    return v.to_dict()

def generate_pdf(html_path, pdf_path):
    """Generate PDF from HTML using generate-pdf.mjs."""
    cmd = ["node", str(PROJECT_ROOT / "generate-pdf.mjs"), html_path, pdf_path]
    ok, stdout, stderr, rc = run_cmd(cmd, timeout=60)
    return {"ok": ok, "stdout": stdout, "stderr": stderr, "path": pdf_path}

def compute_tailoring_delta(base_html_path, tailored_html_path):
    """Compare base vs tailored outputs and compute differences."""
    if not Path(base_html_path).exists() or not Path(tailored_html_path).exists():
        return {"error": "One or both files missing"}

    base_text = Path(base_html_path).read_text()
    tailored_text = Path(tailored_html_path).read_text()

    # Extract body text for comparison
    def extract_text(html):
        # Strip tags and normalize whitespace
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    base_plain = extract_text(base_text)
    tailored_plain = extract_text(tailored_text)

    # Compute diffs
    diff = difflib.unified_diff(
        base_plain.split(),
        tailored_plain.split(),
        lineterm='',
        n=0
    )
    diff_output = list(diff)

    words_added = sum(1 for d in diff_output if d.startswith('+'))
    words_removed = sum(1 for d in diff_output if d.startswith('-'))
    words_total = len(base_plain.split())
    if words_total == 0:
        words_total = 1  # avoid division by zero
    change_pct = round(((words_added + words_removed) / 2) / words_total * 100, 1)

    # Profile summary comparison
    def extract_profile(html):
        m = re.search(r'(?i)(?:profile|summary).*?<h2', html, re.DOTALL)
        if not m:
            m = re.search(r'(?i)(?:profile|summary).*?(?=<h2)', html, re.DOTALL)
        if not m:
            m = re.search(r'(?i)(?:profile|summary).{0,500}', html, re.DOTALL)
        if m:
            return re.sub(r'<[^>]+>', ' ', m.group(0)).strip()[:300]
        return ""

    base_profile = extract_profile(base_text)
    tailored_profile = extract_profile(tailored_text)

    # Count bullets in work experience
    def count_bullets(html):
        return len(re.findall(r'<li>', html, re.IGNORECASE))

    def unique_skills(html):
        skills_match = re.search(r'(?i)skills.*?<h2', html, re.DOTALL)
        if skills_match:
            skill_text = re.sub(r'<[^>]+>', ' ', skills_match.group(0))
        else:
            skill_text = html
        # Extract capitalized words (potential skills)
        skills = set(re.findall(r'\b[A-Z][a-zA-Z+#.]{2,}\b', skill_text))
        return skills

    def count_exp_items(html):
        return len(re.findall(r'class="[^"]*exp-item[^"]*"', html))

    return {
        "words_total": words_total,
        "words_added": words_added,
        "words_removed": words_removed,
        "change_pct": change_pct,
        "bullets_base": count_bullets(base_text),
        "bullets_tailored": count_bullets(tailored_text),
        "exp_items_base": count_exp_items(base_text),
        "exp_items_tailored": count_exp_items(tailored_text),
        "base_profile_preview": base_profile[:200],
        "tailored_profile_preview": tailored_profile[:200],
        "num_diff_lines": len(diff_output),
    }


# ── Main ────────────────────────────────────────────────────────────────
def main():
    results = {}

    print("=" * 80)
    print("CROSS-TEMPLATE REGRESSION TEST")
    print("=" * 80)

    # ═══ STEP 1: Render all templates for all resumes ═══
    print("\n\n### STEP 1: RENDERING ALL TEMPLATES FOR ALL RESUMES ###\n")

    for suite in TEST_SUITES:
        sid = suite["id"]
        print(f"\n--- {suite['name']} ---")
        print(f"    Resume: {suite['resume_path']}")

        # Render v2 + v1 via fill-template.py
        print("    Rendering v2 + v1 (fill-template.py)...")
        v2v1 = render_v2_v1(suite)
        results[f"{sid}_v2v1"] = v2v1
        for tmpl, info in v2v1.items():
            status = "OK" if info["ok"] else "FAIL"
            print(f"      {tmpl}: {status} -> {info['path']}")

        # Render 7 Gemini templates
        print("    Rendering 7 Gemini templates (render_all_templates.py)...")
        gemini = render_gemini_templates(suite)
        results[f"{sid}_gemini"] = gemini
        status = "OK" if gemini["ok"] else "FAIL"
        print(f"      Gemini templates: {status}")
        for tmpl_id, info in gemini.get("templates", {}).items():
            html_status = "HTML:OK" if info["html_exists"] else "HTML:MISSING"
            pdf_status = "PDF:OK" if info["pdf_exists"] else "PDF:MISSING"
            print(f"        {tmpl_id}: {html_status} {pdf_status}")

    # ═══ STEP 2: Validate ALL outputs ═══
    print("\n\n### STEP 2: VALIDATING ALL OUTPUTS ###\n")

    validation_results = defaultdict(dict)

    # Collect all HTML paths
    all_html_paths = {}

    # v2 + v1 outputs
    for suite in TEST_SUITES:
        sid = suite["id"]
        for tmpl in ["v2", "v1"]:
            key = f"{sid}_{tmpl}"
            v2v1 = results.get(f"{sid}_v2v1", {})
            info = v2v1.get(tmpl, {})
            if info.get("ok") and info.get("path"):
                all_html_paths[key] = info["path"]

    # Gemini template outputs
    for suite in TEST_SUITES:
        sid = suite["id"]
        gemini = results.get(f"{sid}_gemini", {})
        for tmpl_id, info in gemini.get("templates", {}).items():
            if info.get("html_exists") and info.get("html_path"):
                key = f"{sid}_gemini_{tmpl_id}"
                all_html_paths[key] = info["html_path"]

    # Also validate existing Nicobar outputs (already generated by council)
    nicobar_dir = PROJECT_ROOT / "output/council/siddharth/nicobar-final"
    for fname in ["nicobar-v2.html", "nicobar-v1.html", "nicobar-resume.html"]:
        p = nicobar_dir / fname
        if p.exists():
            key = f"siddharth-nicobar_existing_{fname.replace('.html', '')}"
            all_html_paths[key] = str(p)

    print(f"Total HTML files to validate: {len(all_html_paths)}")

    for key, path in sorted(all_html_paths.items()):
        if path and Path(path).exists():
            v = validate_html(path)
            validation_results[key] = v
            status = "PASS" if v.get("passed") else "FAIL"
            eco = v.get("error_count", "?")
            wco = v.get("warning_count", "?")
            print(f"  [{status}] {key}: errors={eco}, warnings={wco}")
        else:
            validation_results[key] = {"error": f"Path not found: {path}"}
            print(f"  [SKIP] {key}: file not found")

    # ═══ STEP 3: Calculate tailoring delta ═══
    print("\n\n### STEP 3: TAILORING DELTA ###\n")

    base_v2 = all_html_paths.get("siddharth-base_v2")
    tailored_v2 = all_html_paths.get("siddharth-nicobar_v2")

    if base_v2 and tailored_v2:
        delta = compute_tailoring_delta(base_v2, tailored_v2)
        print(f"  Words total (base): {delta.get('words_total', '?')}")
        print(f"  Words added: {delta.get('words_added', '?')}")
        print(f"  Words removed: {delta.get('words_removed', '?')}")
        print(f"  Change %: {delta.get('change_pct', '?')}%")
        print(f"  Bullets base: {delta.get('bullets_base', '?')}, tailored: {delta.get('bullets_tailored', '?')}")
        print(f"  Exp items base: {delta.get('exp_items_base', '?')}, tailored: {delta.get('exp_items_tailored', '?')}")
        print(f"  Base profile: {delta.get('base_profile_preview', '')[:100]}...")
        print(f"  Tailored profile: {delta.get('tailored_profile_preview', '')[:100]}...")
    else:
        delta = {"error": "Missing base or tailored v2 output"}
        print("  SKIP: Missing base or tailored v2 output")

    # Also compare existing nicobar outputs
    existing_base_v2 = all_html_paths.get("siddharth-nicobar_v2")
    existing_nicobar_v2 = all_html_paths.get("siddharth-nicobar_existing_nicobar-v2")
    if existing_base_v2 and existing_nicobar_v2:
        delta2 = compute_tailoring_delta(existing_base_v2, existing_nicobar_v2)
        print(f"\n  Council vs Manual delta: {delta2.get('change_pct', '?')}% change")

    # ═══ STEP 4: Generate QA report ═══
    print("\n\n### STEP 4: GENERATING QA REPORT ###\n")

    report = build_report(validation_results, delta, results)
    report_path = PROJECT_ROOT / "careerloop/docs/REGRESSION_QA_REPORT.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"QA Report written to: {report_path}")

    # Also save raw JSON for later use
    json_path = PROJECT_ROOT / "output/regression_test/validation_results.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {}
    for k, v in validation_results.items():
        serializable[k] = v
    with open(json_path, "w") as f:
        json.dump(serializable, f, indent=2, default=str)
    print(f"Raw results saved to: {json_path}")

    print("\n" + "=" * 80)
    print("REGRESSION TEST COMPLETE")
    print("=" * 80)


def build_report(validation_results, delta, render_results):
    """Build the QA report markdown."""
    lines = []
    lines.append("# Regression QA Report — 2026-05-18")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("Cross-template regression test across 4 resumes, 9 templates each "
                "(v2, v1, + 7 Gemini templates), validated against 10 rules.")
    lines.append("")

    # ── Summary Table ──
    lines.append("## Results Matrix")
    lines.append("")

    # Define all rules
    rule_ids = ["EM_DASH", "ARROW", "COLLAPSED_BULLETS", "INLINE_BULLETS",
                "FORBIDDEN_SECTION", "ZERO_BULLETS", "SINGLE_BULLET_BLOB",
                "SKILLS_COLLISION", "OVERUSED_TERMS", "ORPHAN_H2"]

    # Collect all template names
    all_keys = sorted(validation_results.keys())

    # Group by resume
    resumes = ["siddharth-nicobar", "siddharth-base", "alex-experienced", "priya-fresher"]
    resume_labels = {
        "siddharth-nicobar": "Siddharth (Nicobar)",
        "siddharth-base": "Siddharth (Base)",
        "alex-experienced": "Alex (Experienced)",
        "priya-fresher": "Priya (Fresher)",
    }

    # Per-template summary
    lines.append("### Template-Level Results")
    lines.append("")
    header = "| Resume | Template | " + " | ".join(r[:10] for r in rule_ids) + " | Status |"
    lines.append(header)
    sep = "|--------|----------|" + "|".join(["--------"] * len(rule_ids)) + "|--------|"
    lines.append(sep)

    for key in all_keys:
        parts = key.split("_", 1)
        resume_id = parts[0]
        template_name = parts[1] if len(parts) > 1 else "unknown"

        v = validation_results.get(key, {})
        if "error" in v:
            lines.append(f"| {resume_id} | {template_name} | " +
                        " | ".join(["SKIP"] * len(rule_ids)) +
                        f" | ERROR: {v['error'][:50]} |")
            continue

        rules = v.get("rules", {})
        row = f"| {resume_id} | {template_name} | "
        for rid in rule_ids:
            ri = rules.get(rid, {})
            if ri.get("passed") is True:
                row += "PASS | "
            elif ri.get("passed") is False:
                row += "FAIL | "
            else:
                row += "N/A | "

        status = "PASS" if v.get("passed") else "FAIL"
        row += f"{status} |"
        lines.append(row)

    # ── Tailoring Delta ──
    lines.append("")
    lines.append("## Tailoring Delta")
    lines.append("")
    lines.append("### Siddharth Base (cv.md) vs Nicobar-Tailored (10_final_resume.md)")
    lines.append("")

    if "error" in delta:
        lines.append(f"> **NOTE:** Delta computation failed: {delta['error']}")
    else:
        # Metrics table
        lines.append("| Metric | Base (cv.md) | Tailored (Nicobar) | Delta |")
        lines.append("|--------|-------------|-------------------|-------|")
        lines.append(f"| Bullets in experience | {delta.get('bullets_base', '?')} | "
                    f"{delta.get('bullets_tailored', '?')} | "
                    f"{delta.get('bullets_tailored', 0) - delta.get('bullets_base', 0):+d} |")
        lines.append(f"| Experience items | {delta.get('exp_items_base', '?')} | "
                    f"{delta.get('exp_items_tailored', '?')} | "
                    f"{delta.get('exp_items_tailored', 0) - delta.get('exp_items_base', 0):+d} |")
        lines.append(f"| Content change | — | — | ~{delta.get('change_pct', '?')}% |")
        lines.append(f"| Diff lines | — | — | {delta.get('num_diff_lines', '?')} |")
        lines.append("")

        # Profile comparison
        lines.append("### Profile Summary Comparison")
        lines.append("")
        lines.append(f"**Base:** {delta.get('base_profile_preview', 'N/A')}...")
        lines.append("")
        lines.append(f"**Tailored:** {delta.get('tailored_profile_preview', 'N/A')}...")
        lines.append("")

    # ── Per-Resume Summary ──
    lines.append("## Per-Resume Summary")
    lines.append("")

    for rid in resumes:
        label = resume_labels.get(rid, rid)
        resume_keys = [k for k in all_keys if k.startswith(rid)]
        passed = sum(1 for k in resume_keys
                    if validation_results.get(k, {}).get("passed") is True
                    and "error" not in validation_results.get(k, {}))
        failed = len(resume_keys) - passed

        # Collect common failures
        failures_by_rule = defaultdict(list)
        for k in resume_keys:
            v = validation_results.get(k, {})
            if "error" in v:
                continue
            for rid in rule_ids:
                ri = v.get("rules", {}).get(rid, {})
                if ri.get("passed") is False:
                    failures_by_rule[rid].append(k.split("_", 1)[1])

        lines.append(f"### {label}")
        lines.append(f"- **Templates tested:** {len(resume_keys)}")
        lines.append(f"- **Passed:** {passed}")
        lines.append(f"- **Failed:** {failed}")
        if failures_by_rule:
            lines.append(f"- **Common failures:**")
            for rid, tkeys in sorted(failures_by_rule.items()):
                lines.append(f"  - {rid}: {', '.join(tkeys[:5])}" +
                            (f" (+{len(tkeys)-5} more)" if len(tkeys) > 5 else ""))
        lines.append("")

    # ── Cross-Cutting Issues ──
    lines.append("## Known Issues (Cross-Cutting)")
    lines.append("")

    # Find rules that fail across all resumes
    global_fail_counts = defaultdict(int)
    for key, v in validation_results.items():
        if "error" in v:
            continue
        for rid in rule_ids:
            ri = v.get("rules", {}).get(rid, {})
            if ri.get("passed") is False:
                global_fail_counts[rid] += 1

    total_valid = sum(1 for v in validation_results.values() if "error" not in v)

    for rid in rule_ids:
        count = global_fail_counts.get(rid, 0)
        if count > 0:
            pct = round(count / total_valid * 100, 1) if total_valid > 0 else 0
            lines.append(f"### {rid} — Fails in {count}/{total_valid} templates ({pct}%)")
            lines.append("")
            # Show examples
            examples = []
            for key, v in validation_results.items():
                if "error" in v:
                    continue
                ri = v.get("rules", {}).get(rid, {})
                if ri.get("passed") is False:
                    examples.append((key, ri.get("details", "")))
            for ek, ed in examples[:5]:
                lines.append(f"- `{ek}`: {ed}")
            lines.append("")

    # ── Overall Verdict ──
    lines.append("## Overall Assessment")
    lines.append("")
    total_tests = total_valid
    total_pass = sum(1 for v in validation_results.values()
                    if v.get("passed") is True and "error" not in v)
    total_fail = total_tests - total_pass

    if total_fail == 0:
        lines.append("**Status: DONE** — All templates pass validation on all resumes.")
    else:
        lines.append(f"**Status: DONE_WITH_CONCERNS** — {total_fail}/{total_tests} templates "
                    f"have validation failures ({round(total_fail/total_tests*100, 1) if total_tests else 0}%).")

    lines.append("")
    lines.append(f"- Total HTML files validated: {total_tests}")
    lines.append(f"- Total passing: {total_pass}")
    lines.append(f"- Total failing: {total_fail}")
    lines.append("")
    lines.append("---")
    lines.append("*Generated by Cross-Template Regression Tester*")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
