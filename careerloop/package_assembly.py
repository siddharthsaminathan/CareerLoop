"""
CareerLoop Package Assembly Layer — Compiles S8 tailored resumes and S3 cached outreach strategy hints.

Generates the professional application package under:
test data/output/{user_id}/packs/{company-slug}/
"""

import os
import re
import json
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from careerloop.rendering.render_all_templates import render_resume

logger = logging.getLogger("careerloop.package_assembly")


class PackageAssembler:
    """Assembles the final, high-fidelity application package for a job."""

    def __init__(self, root_dir: Optional[str] = None):
        self.root = Path(root_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def _company_slug(self, company_name: str) -> str:
        """Normalize company name to standard directory slug."""
        if not company_name:
            return "unknown"
        slug = company_name.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s-]+", "-", slug)
        return slug.strip("-")

    def parse_outreach_hint(self, hint: str) -> Dict[str, Any]:
        """Resiliently parse outreach DM, Exit Line, and Email Guesses from hint text."""
        out = {
            "outreach_dm": "",
            "exit_line": "",
            "email_guesses": []
        }
        if not hint:
            return out

        # Parse DM
        dm_match = re.search(r"DM:\s*(.*?)(?:\n\nExit Line:|\n\nEmail Guesses:|$)", hint, re.DOTALL | re.IGNORECASE)
        if dm_match:
            out["outreach_dm"] = dm_match.group(1).strip()
        else:
            # Fallback if text starts directly without DM: label
            cleaned_hint = hint.replace("OUTREACH PACK:\n", "").strip()
            if "Exit Line:" in cleaned_hint:
                parts = cleaned_hint.split("Exit Line:")
                out["outreach_dm"] = parts[0].strip()

        # Parse Exit Line
        el_match = re.search(r"Exit Line:\s*(.*?)(?:\n\nEmail Guesses:|$)", hint, re.DOTALL | re.IGNORECASE)
        if el_match:
            out["exit_line"] = el_match.group(1).strip()

        # Parse Email Guesses
        eg_match = re.search(r"Email Guesses:\s*(.*)", hint, re.DOTALL | re.IGNORECASE)
        if eg_match:
            guesses_str = eg_match.group(1).strip()
            if guesses_str:
                out["email_guesses"] = [g.strip() for g in guesses_str.split(",") if g.strip()]

        return out

    def assemble_package(self, person_id: str, job_id: str, council_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reads tailored S8 resume and S3 company intel context, compiles PDFs,
        and packages them under `test data/output/{person_id}/packs/{company-slug}/`.
        """
        logger.info(f"Starting package assembly for {person_id} — job {job_id}...")

        # ── 1. Extract context from Council state ──
        company_name = council_state.get("company") or "unknown"
        job_title = council_state.get("job_title") or "unknown"
        original_cv = council_state.get("master_cv") or ""
        
        app_pack = council_state.get("application_pack") or {}
        resume_md = app_pack.get("resume_markdown") or ""
        cover_note = app_pack.get("cover_note") or ""

        # Normalize company name to slug
        company_slug = self._company_slug(company_name)
        pack_dir = self.root / "test data" / "output" / person_id / "packs" / company_slug
        pack_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Target pack directory: {pack_dir}")

        # ── 2. Write S8 resume markdown & cover note ──
        resume_md_path = pack_dir / "resume.md"
        resume_md_path.write_text(resume_md, encoding="utf-8")
        
        cover_note_path = pack_dir / "cover_note.md"
        cover_note_path.write_text(cover_note, encoding="utf-8")

        # ── 3. Compile high-fidelity PDFs via render_resume ──
        # Render PDFs inside a temporary directory to avoid polluting target directory
        temp_render_dir = self.root / "output" / "temp_render" / person_id / job_id
        temp_render_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Triggering Playwright PDF compilation for templates...")
        render_meta = {}
        try:
            render_meta = render_resume(
                input_path=resume_md_path,
                candidate=person_id,
                run_id=job_id,
                out_dir=temp_render_dir,
                generate_pdf=True,
                original_cv_text=original_cv,
                role=job_title,
                company=company_name,
            )
        except Exception as e:
            logger.error(f"Playwright PDF rendering failed: {e}")
            # Non-blocking fallback: try with generate_pdf=False if node generate-pdf.mjs completely crashed
            try:
                render_meta = render_resume(
                    input_path=resume_md_path,
                    candidate=person_id,
                    run_id=job_id,
                    out_dir=temp_render_dir,
                    generate_pdf=False,
                    original_cv_text=original_cv,
                    role=job_title,
                    company=company_name,
                )
            except Exception as e2:
                logger.error(f"Critical HTML rendering fallback failed: {e2}")

        # Locate compiled PDF templates and copy to target directory
        # Siddharth Saminathan -> Siddharth_Saminathan
        safe_name = person_id.title().replace(" ", "_")
        if person_id.lower() == "siddharth":
            safe_name = "Siddharth_Saminathan"

        copied_pdfs = []
        # Target templates we want to export
        target_templates = {
            "classic-ats": f"{safe_name}_Resume_{company_name}_ATS.pdf",
            "product-engineer": f"{safe_name}_Resume_{company_name}_Product_Engineer.pdf",
        }

        for tmpl_id, target_filename in target_templates.items():
            pdf_source = temp_render_dir / f"{tmpl_id}.pdf"
            if pdf_source.exists():
                pdf_target = pack_dir / target_filename
                shutil.copy2(pdf_source, pdf_target)
                copied_pdfs.append(str(pdf_target))
                logger.info(f"Copied compiled PDF: {target_filename}")
            else:
                logger.warning(f"Compiled PDF not found for template: {tmpl_id}")

        # Clean up temp rendering directory
        try:
            shutil.rmtree(temp_render_dir)
        except Exception:
            pass

        # ── 4. Extract and parse outreach metadata ──
        company_intel = council_state.get("company_intelligence") or {}
        # Support both object and dictionary structures
        if not isinstance(company_intel, dict):
            try:
                company_intel = company_intel.to_dict()
            except Exception:
                company_intel = {}

        recruiter_info = company_intel.get("recruiter_info") or {}
        outreach_strategy_hint = company_intel.get("outreach_strategy_hint") or ""

        # Parse outreach pack elements
        parsed_outreach = self.parse_outreach_hint(outreach_strategy_hint)
        
        # Prioritize System 8 finalized humanized recruiter message
        finalized_dm = app_pack.get("recruiter_message") or ""
        outreach_dm = finalized_dm if finalized_dm else parsed_outreach["outreach_dm"]
        if not outreach_dm:
            outreach_dm = "Hey, I saw the open role at your company and wanted to connect to share my experience in AI engineering."

        route = recruiter_info.get("route") or "Route C"
        reason = recruiter_info.get("reason") or "Implicit outreach targeting EM/Recruiter leads."
        target_name = recruiter_info.get("name") or "Hiring Manager"
        target_role = recruiter_info.get("role") or "Engineering / Product Leadership"
        target_link = recruiter_info.get("link") or ""
        plausibility = recruiter_info.get("plausibility_score") or "3"

        # Direct LinkedIn vs search query fallback
        is_unknown = not target_name or target_name.upper() == "UNKNOWN" or target_name == "Hiring Manager"
        
        import urllib.parse
        
        # Pre-compute direct Company Search Link on LinkedIn
        company_search_query = f"{company_name}"
        company_linkedin_search_url = f"https://www.linkedin.com/search/results/companies/?keywords={urllib.parse.quote(company_search_query)}"
        company_slug = self._company_slug(company_name)
        company_direct_linkedin_url = f"https://www.linkedin.com/company/{company_slug}"
        
        # Pre-compute direct Job Search Link on LinkedIn
        job_search_query = f"{job_title} {company_name}"
        job_linkedin_search_url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(job_search_query)}"
        
        # Pre-compute multiple hyper-targeted search links to prevent LinkedIn search failures
        recruiter_search_url = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(f'{company_name} Recruiter')}"
        ta_search_url = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(f'{company_name} Talent Acquisition')}"
        eng_search_url = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(f'{company_name} Head of Engineering')}"
        
        person_search_url = ""
        if not is_unknown:
            person_search_url = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(f'{target_name} {company_name}')}"
 
        # ── 5. Generate human-readable outreach_pack.md ──
        email_bullets = "\n".join(f"- `{email}`" for email in parsed_outreach["email_guesses"]) if parsed_outreach["email_guesses"] else "- *No corporate email guesses found*"
        
        # Build target link section with robust, working individual search fallbacks
        target_link_str = ""
        if target_link:
            target_link_str += f"[{target_link}]({target_link})"
        else:
            target_link_str += "*Not available*"
        
        if person_search_url:
            target_link_str += f"\n* **LinkedIn Direct Search Link (Fallback):** [Search '{target_name} {company_name}' on LinkedIn]({person_search_url})"
            
        target_link_str += f"\n* **LinkedIn Recruiter Search Fallback:** [Search '{company_name} Recruiter' on LinkedIn]({recruiter_search_url})"
        target_link_str += f"\n* **LinkedIn TA Search Fallback:** [Search '{company_name} Talent Acquisition' on LinkedIn]({ta_search_url})"
        target_link_str += f"\n* **LinkedIn Engineering Head Search Fallback:** [Search '{company_name} Head of Engineering' on LinkedIn]({eng_search_url})"

        # Clean Job URL fallback
        job_url_str = council_state.get("job_url") or "Not provided"
        job_url_display = ""
        if job_url_str and job_url_str != "Not provided":
            job_url_display = f"[{job_url_str}]({job_url_str})"
        else:
            job_url_display = "*Not provided*"
            
        # Always append a search for this job on LinkedIn
        job_url_display += f"\n* **LinkedIn Job Search Link (Fallback):** [Search '{job_title}' jobs at {company_name}]({job_linkedin_search_url})"

        outreach_md_content = f"""# Application & Outreach Pack — {company_name}

## 📡 Route Classification
* **Route Assigned:** **{route}**
* **Reasoning:** {reason}
* **Original Job Posting URL:** {job_url_display}

## 🎯 Target Lead Profile
* **Name:** {target_name}
* **Role/Title:** {target_role}
* **LinkedIn URL:** {target_link_str}
* **Company LinkedIn Page:** [{company_name} LinkedIn Page]({company_direct_linkedin_url}) (Fallback: [Search {company_name} on LinkedIn]({company_linkedin_search_url}))
* **Plausibility Match Score:** {plausibility}/5

---

## 💬 Humanized LinkedIn DM Outreach
*Strict Anti-AI guidelines enforced: zero jargon, under 120 words, metric-dense, peer-to-peer cadence.*

```text
{outreach_dm}
```

## 🚪 Exit Line (CTA)
```text
{parsed_outreach["exit_line"] or "Let me know if you have 5 minutes to chat."}
```

---

## 📧 Corporate Email Guesses
Standard domain name combinations calculated for this contact:
{email_bullets}
"""

        outreach_md_path = pack_dir / "outreach_pack.md"
        outreach_md_path.write_text(outreach_md_content, encoding="utf-8")
        logger.info("Saved outreach_pack.md")

        # ── 6. Save machine-readable pack_metadata.json ──
        metadata = {
            "job_id": job_id,
            "company": company_name,
            "company_slug": company_slug,
            "job_title": job_title,
            "route_classified": route,
            "route_reason": reason,
            "target_contact": {
                "name": target_name,
                "role": target_role,
                "linkedin_url": target_link,
                "plausibility_score": plausibility
            },
            "outreach_dm": parsed_outreach["outreach_dm"],
            "exit_line": parsed_outreach["exit_line"],
            "email_guesses": parsed_outreach["email_guesses"],
            "compiled_files": {
                "resume_markdown": "resume.md",
                "cover_note": "cover_note.md",
                "outreach_pack": "outreach_pack.md",
                "pdfs": [os.path.basename(p) for p in copied_pdfs]
            }
        }

        metadata_path = pack_dir / "pack_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved pack_metadata.json")

        print(f"✅ E2E Package Assembly Completed successfully under: {pack_dir}")

        return {
            "pack_dir": str(pack_dir),
            "metadata_path": str(metadata_path),
            "pdfs": copied_pdfs
        }
