import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional, Dict

from typing_extensions import TypedDict

from langgraph.graph import END, StateGraph

from careerloop.council.llm import CouncilLLMClient
from careerloop.council.schemas import validate_payload, schema_instruction
from careerloop.council.models import (
    CanonicalResume,
    ResumeSection,
    PreservationContract,
    CompanyIntelligence,
    RoleDecode,
    UserTruth,
    PositioningStrategy,
    SectionRewrites,
    SectionRewrite,
    ApplicationPack,
    QualityReport,
    LinkAudit,
)
from careerloop.council.compiler import ResumeCompiler
from careerloop.council.humanizer import Humanizer
from careerloop.council.node_result import NodeResult
from careerloop.council.runtime_context import get_runtime_context


# ─── State ────────────────────────────────────────────────────────────────────

class CouncilState(TypedDict):
    # Inputs
    job_id: str
    person_id: str
    job_title: str
    company: str
    job_url: str
    jd_text: str
    master_cv: str
    profile: dict
    today: str

    # Artifacts (The 8 Systems)
    canonical_resume: Optional[Dict]
    preservation_contract: Optional[Dict]
    company_intelligence: Optional[Dict]
    role_decode: Optional[Dict]
    user_truth: Optional[Dict]
    positioning_strategy: Optional[Dict]
    section_rewrites: Optional[Dict]
    application_pack: Optional[Dict]
    truth_guard_report: Optional[Dict]
    pre_humanizer_resume: Optional[str]
    humanizer_output: Optional[str]  # post-humanizer resume (the actual deliverable)
    humanizer_report: Optional[Dict]
    s7_debug: Optional[Dict]  # per-section timing, model, rewrite stats

    candidate_graph: Optional[Dict]    # structured CandidateGraph (wired in S1)
    cv_tenure_years: Optional[float]   # CV-verified non-overlapping tenure (B9 fix)

    errors: list


# ─── LLM client ───────────────────────────────────────────────────────────────

def _call(system: str, user: str, temperature: float = 0.2,
          max_tokens: int = None, label: str = "", model_kind: str = "writer",
          retries: int = 0) -> NodeResult:
    """Call the LLM and return a structured NodeResult.

    Args:
        model_kind: "strategy" → deepseek-v4-pro (S3-S6)
                    "writer"   → deepseek-chat    (S7-S8: rewrites, cover, DM)
        retries:    Number of extra attempts on empty/parse-error response.

    NEVER raises — failures are captured in NodeResult.success=False.
    """
    import time
    tag = f" [{label}]" if label else ""
    for attempt in range(retries + 1):
        client = CouncilLLMClient(model_kind)
        client.temperature = temperature
        retry_tag = " (retry)" if attempt > 0 else ""
        print(f"  ⟳ LLM call{tag}{retry_tag}...", end=" ", flush=True)
        try:
            payload = client.complete_json(system, user, max_tokens=max_tokens)
            if payload.get("_parse_error") and attempt < retries:
                print(f"empty — retrying in 2s")
                time.sleep(2)
                continue
            if isinstance(payload, dict) and not any(v for v in payload.values() if v):
                if attempt < retries:
                    print(f"all-empty response — retrying in 2s")
                    time.sleep(2)
                    continue
            print("done")
            return NodeResult(success=True, confidence=0.8, payload=payload)
        except Exception as e:
            if attempt < retries:
                print(f"error ({e}) — retrying in 2s")
                time.sleep(2)
                continue
            print(f"FAILED")
            print(f"  !! LLM Call error: {e}")
            return NodeResult(success=False, confidence=0.0, errors=[str(e)])
    print("FAILED (all retries exhausted)")
    return NodeResult(success=False, confidence=0.0, errors=["all retries exhausted"])


def _has_errors(state: CouncilState) -> bool:
    """Return True if any prior node accumulated errors."""
    return bool(state.get("errors"))


def _split_section_into_chunks(text: str, max_chunk_chars: int = 1500) -> list:
    """Split a long section into chunks at paragraph (double-newline) boundaries.

    Each chunk is at most max_chunk_chars characters.  Paragraphs that are
    themselves longer than the limit are kept as a single chunk — we never
    split mid-paragraph.

    Returns a list of non-empty chunk strings.  Falls back to [text] if
    splitting produces nothing useful.
    """
    paragraphs = [p for p in re.split(r'\n{2,}', text.strip()) if p.strip()]
    if not paragraphs:
        return [text]

    chunks = []
    current: list = []
    current_len = 0

    for para in paragraphs:
        plen = len(para)
        if current and current_len + plen > max_chunk_chars:
            chunks.append('\n\n'.join(current))
            current = [para]
            current_len = plen
        else:
            current.append(para)
            current_len += plen

    if current:
        chunks.append('\n\n'.join(current))

    return chunks if chunks else [text]


def _split_by_job_boundaries(text: str) -> list[str]:
    """Split an experience section into one chunk per employer entry.

    Detects job-entry boundaries by finding lines that:
      1. Start with an uppercase letter (company name / section header)
      2. Are NOT bullet lines (no leading -, *, +)
      3. Are followed within 3 lines by a date/tenure pattern (month, year,
         "Present", or an en-dash date range)

    This eliminates the cross-job bullet attribution error that occurs when
    the LLM receives a 3000+ char flat block spanning multiple employers and
    mis-assigns a bullet from job A to job B.

    Returns [text] (single chunk = whole section) when fewer than 2 job
    boundaries are detected — the caller falls back to paragraph chunking.
    """
    _date_pat = re.compile(
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present|\d{4})\b',
        re.I,
    )
    _bullet_pat = re.compile(r'^\s*[-*+]\s+')

    lines = text.splitlines()
    job_start_indices: list[int] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if _bullet_pat.match(line):
            continue  # bullets are never job headers
        if not stripped[0].isupper():
            continue  # lowercase-starting line = prose continuation
        # Skip lines that contain a date themselves — those are role/date lines
        # ("Category Manager – Fashion Nov 2025 – Present"), not company-name lines.
        # Company-name lines like "Acme Corp, Bangalore, India" don't contain dates.
        if _date_pat.search(stripped):
            continue
        # Check: does a date pattern appear within the next 3 non-blank lines?
        # (The role/date line immediately follows the company-name line.)
        nearby: list[str] = []
        for j in range(i + 1, min(i + 5, len(lines))):
            if lines[j].strip():
                nearby.append(lines[j])
            if len(nearby) == 3:
                break
        if any(_date_pat.search(nl) for nl in nearby):
            job_start_indices.append(i)

    if len(job_start_indices) < 2:
        return [text]  # can't split meaningfully

    chunks: list[str] = []
    for idx, start in enumerate(job_start_indices):
        end = job_start_indices[idx + 1] if idx + 1 < len(job_start_indices) else len(lines)
        chunk_lines = lines[start:end]
        # Strip leading/trailing blank lines from each chunk
        while chunk_lines and not chunk_lines[0].strip():
            chunk_lines.pop(0)
        while chunk_lines and not chunk_lines[-1].strip():
            chunk_lines.pop()
        if chunk_lines:
            chunks.append('\n'.join(chunk_lines))

    return chunks if len(chunks) >= 2 else [text]


def _count_markdown_bullets(text: str) -> int:
    return len(re.findall(r"(?m)^\s*[-*]\s+\S", text or ""))


def _rewrite_preserves_section_structure(original: str, rewritten: str) -> tuple[bool, list[str]]:
    issues: list[str] = []

    original_bullets = _count_markdown_bullets(original)
    rewritten_bullets = _count_markdown_bullets(rewritten)
    if original_bullets > 3 and rewritten_bullets < (original_bullets * 0.5):
        issues.append(f"bullet_count_dropped:{original_bullets}->{rewritten_bullets}")

    # [^\S\n]+ = whitespace EXCLUDING newline — prevents matching across lines.
    # "Built X.\n- Designed Y" is valid markdown, not a collapsed bullet.
    if re.search(r"\.[^\S\n]+[-*]\s+[A-Z0-9]", rewritten or ""):
        issues.append("collapsed_bullet_marker")

    if re.search(r"(?m)^\s*\*\*\s*$", rewritten or ""):
        issues.append("orphan_emphasis_marker")

    original_has_heading = bool(re.search(r"(?m)^\s{0,3}#{1,6}\s+\S", original or ""))
    rewritten_has_heading = bool(re.search(r"(?m)^\s{0,3}#{1,6}\s+\S", rewritten or ""))
    if rewritten_has_heading and not original_has_heading:
        issues.append("injected_heading_marker")

    stripped = (rewritten or "").strip()
    # Only check truncation on sections that use bullet markers in the original.
    # Skills, languages, contact — these legitimately end without punctuation.
    if stripped and original_bullets > 0:
        last_line = stripped.rsplit("\n", 1)[-1].strip()
        ends_cleanly = last_line.endswith((".", ")", "]", ":", "%", "|", "/"))
        has_bullet_near_end = "\n- " in stripped[-120:]
        if (not ends_cleanly
                and not has_bullet_near_end
                and len(last_line) > 60
                and last_line[-1:].isalpha() and last_line[-1:].islower()):
            issues.append("possible_truncation")

    orig_len = len((original or "").strip())
    if orig_len >= 60 and len(stripped) < orig_len * 0.35:
        issues.append(f"rewrite_too_short:{len(stripped)}<{orig_len}")

    return not issues, issues


def _strip_generated_heading_prefix(text: str, section_title: str) -> str:
    """Remove accidental heading wrappers that S7 sometimes returns."""
    out = (text or "").strip()
    if not out:
        return out

    # Strip any leading/trailing loose ** markers
    out = re.sub(r"^\s*\*\*\s*\n+", "", out)
    
    # Check if the first line is a heading
    lines = out.splitlines()
    while lines:
        first = lines[0].strip()
        first_clean = first.strip("*").strip()
        if first_clean.startswith("#"):
            heading = first_clean.lstrip("#").strip().lower()
            target = (section_title or "").strip().lower()
            if heading == target or heading in {"education", "skills", "summary", "profile", "work experience", "professional experience"}:
                lines = lines[1:]
                # if there is a loose ** right after the heading, strip it too
                while lines and not lines[0].strip():
                    lines = lines[1:]
                if lines and lines[0].strip() == "**":
                    lines = lines[1:]
                continue
        # Also remove any stray ** lines at the top
        if first == "**" or first == "*":
            lines = lines[1:]
            continue
        break
        
    while lines and not lines[0].strip():
        lines = lines[1:]
        
    out = "\n".join(lines).strip()
    out = re.sub(r"\n+\s*\*\*\s*$", "", out)
    return out


def _is_identity_or_contact_section(section: dict) -> bool:
    section_id = (section.get("section_id") or "").strip().lower()
    normalized_type = (section.get("normalized_type") or "").strip().lower()
    raw = section.get("raw_text") or ""

    if section_id == "intro" or normalized_type == "contact":
        return True

    has_email = bool(re.search(r"[\w.+-]+@[\w.-]+\.\w+", raw))
    has_phone = bool(re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", raw))
    if (has_email or has_phone) and len(raw) < 420:
        return True

    return False


def _payload_to_rewritten_text(payload: dict, original: str, normalized_type: str = "") -> str:
    """Bridge S7 structured output into the legacy assembler contract.

    Handles two LLM response shapes:
      - rewritten_text: full section markdown → use directly.
      - tailored_bullets: list of bare bullet strings (no headers/dates/company lines).

    For tailored_bullets, dispatches to one of four paths based on section type:

    Path 1 — profile/summary:
        Single-paragraph rewrite: return the single cleaned bullet as a paragraph.

    Path 2 — flat-list sections (skills/technical_skills/core_competencies/tools):
        No structural scaffold to preserve.  Just output the LLM bullets as a
        flat "- X" list.  This avoids the wrapping-artifact problem (PDF-extracted
        skills like "- Inventory\\nControl" would confuse scaffold reconstruction).

    Path 3 — scaffold sections (experience, projects, etc.):
        Preserve structural non-bullet lines (company name, role, dates, intro
        paragraphs) and substitute each bullet one-for-one with its rewrite.

        Two fixes over the naïve approach:
          a) Continuation-line skipping: after replacing a bullet, enter
             "continuation" state.  While in that state, skip non-blank lines
             that start with a lowercase letter — these are wrapped continuations
             of the replaced multi-line bullet (PDF extraction artefact).
             Reset the state on a blank line or a line that starts with an
             uppercase letter (structural element: company name, date, title).
          b) Excess-original-bullet skipping: if the LLM returned FEWER bullets
             than the original (intentional consolidation, e.g. skills grouping),
             remaining original bullets are skipped so un-tailored originals
             don't leak into the output.

    Path 4 — no bullets in original:
        Join the cleaned bullets as newline-separated paragraphs.
    """
    direct = (payload.get("rewritten_text") or "").strip()
    items = payload.get("tailored_bullets")
    normalized = (normalized_type or "").lower()

    # Scaffold sections (experience / projects) must go through Path 3 so that
    # company names, job titles, and date ranges are preserved via scaffold
    # reconstruction.  When the LLM returns only rewritten_text (no
    # tailored_bullets), extract the bullet lines from it and treat them as
    # tailored_bullets so scaffold reconstruction still runs.
    _scaffold_sections = {"experience", "work_experience", "projects", "project"}
    if direct:
        if normalized not in _scaffold_sections:
            # Non-scaffold section — use the full rewrite directly.
            return direct
        if not isinstance(items, list):
            # Scaffold section but only rewritten_text returned: extract bullets.
            items = [
                re.sub(r"^\s*[-*+]\s+", "", ln).strip()
                for ln in direct.splitlines()
                if re.match(r"^\s*[-*+]\s+\S", ln)
            ]
            if not items:
                # LLM returned prose paragraphs with no bullet markers (DeepSeek
                # non-determinism).  Split on blank lines and treat each paragraph
                # as a bullet, but skip structural lines (company header / date line /
                # description preamble) — those are re-injected by the scaffold
                # reconstruction below.
                _date_hdr = re.compile(
                    r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present|\d{4})\b',
                    re.I,
                )
                raw_paragraphs = [p.strip() for p in re.split(r"\n{2,}", direct) if p.strip()]
                items = []
                for p in raw_paragraphs:
                    # Skip if paragraph's FIRST LINE looks like a structural header
                    # (contains a date pattern — job title / company / date line).
                    first_line = p.splitlines()[0]
                    if _date_hdr.search(first_line):
                        continue
                    # Skip very short paragraphs (description prose like "An AI system...")
                    if len(p) < 60:
                        continue
                    items.append(p)
                if not items:
                    return direct
        # Fall through to the bullet-based paths below (tailored_bullets or extracted).

    if not isinstance(items, list):
        return ""

    # Clean each bullet: strip markdown prefixes, bold markers, and heading syntax
    cleaned: list[str] = []
    for item in items:
        text = str(item or "").strip()
        text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text)
        text = re.sub(r"^\s*[-*+]\s+", "", text)
        text = text.strip("*").strip()
        if text:
            cleaned.append(text)

    if not cleaned:
        return ""

    original_bullets = len(re.findall(r"(?m)^\s*[-*+]\s+\S", original or ""))
    # NOTE: `normalized` was already computed above alongside `direct` and `items`.

    # ── Path 1: profile / summary ──────────────────────────────────────────────
    if normalized in {"profile", "summary"} and len(cleaned) == 1:
        return cleaned[0]

    # ── Path 2: flat-list sections (skills, tools, etc.) ──────────────────────
    # No structural scaffold worth preserving.  Output LLM bullets as flat list.
    # This avoids both continuation-line confusion and excess-original-bullet
    # leakage for sections whose structure is purely a list of items.
    # Note: normalized_type may be "skill" (singular) or "skills" (plural) depending on
    # the normalizer — include both to be safe.
    if normalized in {"skill", "skills", "technical_skills", "core_competencies", "tools"}:
        return "\n".join(f"- {b}" for b in cleaned)

    # ── Path 3: scaffold-preserving reconstruction ─────────────────────────────
    if original_bullets > 0:
        orig_lines = (original or "").splitlines()
        result_lines: list[str] = []
        bullet_idx = 0
        _bullet_pat = re.compile(r"^\s*[-*+]\s+\S")
        in_continuation = False  # True while consuming a replaced bullet's wrapped lines

        for line in orig_lines:
            if _bullet_pat.match(line):
                if bullet_idx < len(cleaned):
                    result_lines.append(f"- {cleaned[bullet_idx]}")
                    bullet_idx += 1
                # Whether we consumed a rewrite or not, the next non-blank non-bullet
                # lines may be continuations of this wrapped bullet.
                in_continuation = True
            elif in_continuation:
                stripped = line.strip()
                if not stripped:
                    # Blank line → end of bullet continuation
                    in_continuation = False
                    result_lines.append(line)
                elif stripped[0].islower():
                    # Lowercase-start → sentence continuation of the previous wrapped
                    # bullet (PDF hard-wrap artefact).  Skip it.
                    pass
                elif stripped[-1] in {'.', ',', ';', '…'}:
                    # Uppercase-start BUT ends with sentence punctuation → still a
                    # sentence fragment continuation (e.g. "India and Asia, ensuring
                    # 95% on-time delivery for seasonal production orders.").  Skip it.
                    pass
                else:
                    # Uppercase-start + no terminal sentence punctuation →
                    # structural element (company name, date range, job title).
                    # Keep it and exit continuation mode.
                    in_continuation = False
                    result_lines.append(line)
            else:
                result_lines.append(line)

        # Append any excess LLM bullets not consumed by the scaffold
        while bullet_idx < len(cleaned):
            result_lines.append(f"- {cleaned[bullet_idx]}")
            bullet_idx += 1

        return "\n".join(result_lines)

    # ── Path 4: no bullets in original ────────────────────────────────────────
    return "\n\n".join(cleaned)


def _rewrite_one_section(
    section: dict,
    tone: str,
    narrative_angle: str,
    things_to_downplay: list,
    role_keywords: list,
    hidden_expectations: list,
    day_one_deliverables: list,
    must_haves: list,
    proof_points: list,
    claims_allowed: list,
    claims_not_allowed: list,
    s7_rewrite_context: dict | None = None,
) -> tuple:
    """Worker for parallel S7 execution.

    Handles both chunked (large experience sections) and standard rewrites.
    Returns (sid, rewrite_dict_or_None, skip_reason_or_None).
    Thread-safe: _call() creates a new CouncilLLMClient per invocation.
    """
    sid = section.get('section_id', '')
    stitle = section.get('section_title', sid)
    raw = section.get('raw_text', '')
    normalized_type = section.get('normalized_type', '')

    is_experience = normalized_type in {
        "experience", "work_experience", "professional_experience"
    }

    # ── Chunked path for experience sections ──────────────────────────────
    # For experience sections: ALWAYS attempt job-boundary splitting (one chunk
    # per employer). This eliminates cross-job bullet attribution errors that
    # arise when multiple employers live in one flat LLM call.
    # Fall back to paragraph chunking only if job detection returns 1 chunk.
    if is_experience:
        chunks = _split_by_job_boundaries(raw)
        if len(chunks) == 1 and len(raw) > 1800:
            # Job-boundary detection failed — fall back to paragraph chunking.
            chunks = _split_section_into_chunks(raw, max_chunk_chars=1400)
        if len(chunks) == 1:
            # Single employer or short section — use the normal (non-chunked) path.
            chunks = None  # signal to fall through to single-section path
    else:
        chunks = None

    if chunks is None and len(raw) > 1800 and not is_experience:
        chunks = _split_section_into_chunks(raw, max_chunk_chars=1400)

    if chunks is not None and len(chunks) > 1:
        print(f"  → S7 chunked '{sid}' ({len(raw)} chars) → {len(chunks)} chunks")
        rewritten_chunks = []
        chunk_ok = True

        for ci, chunk in enumerate(chunks):
            chunk_prompt_dict = {
                "section_id": f"{sid}_chunk{ci + 1}",
                "section_title": stitle,
                "section_text": chunk,
                "tone_guidance": tone,
                "narrative_angle": narrative_angle,
                "role_keywords": role_keywords,
                "must_haves": must_haves,
                "hidden_expectations": hidden_expectations,
                "day_one_deliverables": day_one_deliverables,
                "things_to_downplay": things_to_downplay,
                "proof_points": proof_points,
                "claims_allowed": claims_allowed,
                "claims_not_allowed": claims_not_allowed,
            }
            if s7_rewrite_context:
                chunk_prompt_dict["company_context"] = s7_rewrite_context
            chunk_prompt = json.dumps(chunk_prompt_dict, ensure_ascii=False)

            cresult = _call(
                _S7_PER_SECTION_SYSTEM, chunk_prompt,
                label=f"S7 {sid} {ci + 1}/{len(chunks)}",
                model_kind="writer", retries=1,
            )
            if not cresult.success:
                print(f"  !! S7 chunk {ci + 1} failed — aborting chunked rewrite for '{sid}'")
                chunk_ok = False
                break

            ctext = _payload_to_rewritten_text(cresult.payload, chunk, normalized_type).strip()
            if not ctext or len(ctext) < len(chunk) * 0.4:
                print(
                    f"  !! S7 chunk {ci + 1} truncated "
                    f"({len(ctext)} vs {len(chunk)} chars) — aborting"
                )
                chunk_ok = False
                break

            # For scaffold sections: the LLM sometimes drops the company name / role /
            # date header when rewriting an intro-only chunk (one that has no bullets).
            # Extract the first two structural lines from the original chunk and prepend
            # them to the rewrite if they are absent.
            if normalized_type in {"experience", "work_experience"}:
                orig_chunk_lines = [l for l in chunk.splitlines() if l.strip()]
                # Structural header = first two non-blank lines (company + role/date).
                # Stop before any bullet line or prose continuation (starts lowercase).
                struct_lines: list[str] = []
                for ol in orig_chunk_lines[:4]:
                    stripped = ol.strip()
                    if re.match(r"^\s*[-*+]\s+\S", ol):
                        break  # reached bullets — stop
                    if struct_lines and stripped and stripped[0].islower():
                        break  # continuation prose — stop
                    if stripped:
                        struct_lines.append(stripped)
                    if len(struct_lines) == 2:
                        break  # only need company + role/date

                if struct_lines:
                    # Check if the first structural line (company name) appears in ctext.
                    first_key = struct_lines[0].lower()[:20]
                    if first_key not in ctext.lower():
                        preamble = "\n".join(struct_lines)
                        ctext = preamble + "\n" + ctext

            rewritten_chunks.append(_strip_generated_heading_prefix(ctext, stitle))

        if not chunk_ok or not rewritten_chunks:
            reason = "chunked_rewrite_failed"
            print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
            return sid, None, reason

        rewritten = '\n\n'.join(rewritten_chunks)
        rewritten = _strip_generated_heading_prefix(rewritten, stitle)
        rewritten = ResumeCompiler._preprocess_plaintext_cv(rewritten)
        safe, issues = _rewrite_preserves_section_structure(raw, rewritten)
        # For chunked sections scaffold reconstruction already runs per-chunk, preserving
        # company headers, dates and role lines. The LLM intentionally consolidates many
        # original bullets into fewer, higher-quality tailored bullets — this is correct
        # behaviour, not structural damage. Only hard-fail on real corruption signals.
        issues = [i for i in issues if not i.startswith("bullet_count_dropped")]
        safe = len(issues) == 0
        if not safe:
            reason = f"chunk_structure_check_failed:{','.join(issues)}"
            print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
            return sid, None, reason
        rewrite_dict = {
            "section_id": sid,
            "original_text": raw,
            "rewritten_text": rewritten,
            "change_type": "REWRITE",
            "change_reason": f"Chunked rewrite ({len(chunks)} chunks, {len(raw)} → {len(rewritten)} chars)",
            "claims_added": [],
            "claims_removed": [],
            "evidence_used": [],
            "risk_level": "medium",
        }
        print(f"  → [CHUNKED] {stitle} ({len(rewritten)} chars from {len(chunks)} chunks)")
        return sid, rewrite_dict, None

    # ── Standard single-call rewrite ──────────────────────────────────────
    prompt_dict = {
        "section_id": sid,
        "section_title": stitle,
        "section_text": raw,
        "tone_guidance": tone,
        "narrative_angle": narrative_angle,
        "role_keywords": role_keywords,
        "must_haves": must_haves,
        "hidden_expectations": hidden_expectations,
        "day_one_deliverables": day_one_deliverables,
        "things_to_downplay": things_to_downplay,
        "proof_points": proof_points,
        "claims_allowed": claims_allowed,
        "claims_not_allowed": claims_not_allowed,
    }
    if s7_rewrite_context:
        prompt_dict["company_context"] = s7_rewrite_context
    prompt = json.dumps(prompt_dict, ensure_ascii=False)

    result = _call(_S7_PER_SECTION_SYSTEM, prompt, label=f"S7 {sid}", model_kind="writer", retries=1)
    if not result.success:
        reason = f"llm_error:{result.errors}"
        print(f"  !! S7 fallback '{sid}' → {reason}")
        return sid, None, reason

    payload = result.payload
    rewritten = _payload_to_rewritten_text(payload, raw, normalized_type).strip()
    if not rewritten:
        reason = "empty_rewrite"
        print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
        return sid, None, reason

    # Truncation guard — use bullet-aware comparison when LLM returned tailored_bullets.
    # tailored_bullets path: _payload_to_rewritten_text already reconstructs the full
    # section (headers + dates preserved), so length should be close to original.
    # For rewritten_text path: plain 50% length guard.
    if payload.get("tailored_bullets") and not payload.get("rewritten_text"):
        # Compare bullet content only, not total length (headers/dates are preserved by reconstruction)
        orig_bullet_text = " ".join(
            m.group(0) for m in re.finditer(r"(?m)^\s*[-*+]\s+.+", raw or "")
        )
        rew_bullet_text = " ".join(
            m.group(0) for m in re.finditer(r"(?m)^\s*[-*+]\s+.+", rewritten or "")
        )
        if orig_bullet_text and len(rew_bullet_text) < len(orig_bullet_text) * 0.3:
            reason = f"bullet_truncation_suspected:{len(rew_bullet_text)}<{len(orig_bullet_text)}*0.3"
            print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
            return sid, None, reason
    elif len(rewritten) < len(raw) * 0.5:
        reason = f"truncation_suspected:rewrite={len(rewritten)}chars,original={len(raw)}chars"
        print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
        return sid, None, reason

    rewritten = _strip_generated_heading_prefix(rewritten, stitle)
    rewritten = ResumeCompiler._preprocess_plaintext_cv(rewritten)
    # Skip structure check for flat-list sections (skills, tools, etc.) — these
    # sections intentionally consolidate many fine-grained bullets into a few
    # grouped categories.  Bullet-count parity is not expected or required.
    _flat_normalized = {"skill", "skills", "technical_skills", "core_competencies", "tools"}
    if normalized_type not in _flat_normalized:
        safe, issues = _rewrite_preserves_section_structure(raw, rewritten)
        if not safe:
            reason = f"structure_check_failed:{','.join(issues)}"
            print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
            return sid, None, reason

    rewrite_dict = {
        "section_id": sid,
        "original_text": raw,
        "rewritten_text": rewritten,
        "change_type": payload.get('change_type', 'REWRITE'),
        "change_reason": payload.get('change_reason', ''),
        "claims_added": payload.get('claims_added', []),
        "claims_removed": payload.get('claims_removed', []),
        "evidence_used": payload.get('evidence_used', []),
        "risk_level": payload.get('risk_level', 'low'),
    }
    print(f"  → [{payload.get('change_type','?')}] {stitle} ({len(rewritten)} chars)")
    return sid, rewrite_dict, None


# ─── System 1: Document Parser ───────────────────────────────────────────────

def parse_node(state: CouncilState) -> CouncilState:
    print("\n--- System 1: Document Parser ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    try:
        from careerloop.council.truth_guard import compute_cv_tenure_years
        resume = ResumeCompiler.parse_markdown(state["master_cv"])
        resume_dict = resume.to_dict()

        # ── CandidateGraph (structured bullet extraction) ──────────────
        try:
            candidate_graph = ResumeCompiler.extract_candidate_graph(resume_dict)
            print(f"  → CandidateGraph: {len(candidate_graph.get('experience', []))} experience blocks, "
                  f"{len(candidate_graph.get('metric_vault', []))} metrics")
        except Exception as cg_err:
            print(f"  !! CandidateGraph extraction failed (non-fatal): {cg_err}")
            candidate_graph = None

        # ── CV tenure (B9 fix: regex-parsed non-overlapping years) ─────
        try:
            experience_texts = [
                s.get("raw_text", "")
                for s in resume_dict.get("sections", [])
                if (s.get("section_type") or "").lower() == "experience"
                   or "experience" in (s.get("section_title") or "").lower()
            ]
            cv_tenure_years = compute_cv_tenure_years(experience_texts) if experience_texts else None
            if cv_tenure_years is not None:
                print(f"  → CV tenure (verified): {cv_tenure_years} years")
        except Exception as tenure_err:
            print(f"  !! CV tenure computation failed (non-fatal): {tenure_err}")
            cv_tenure_years = None

        return {**state, "canonical_resume": resume_dict,
                "candidate_graph": candidate_graph,
                "cv_tenure_years": cv_tenure_years}
    except Exception as e:
        msg = f"Document Parser failed: {e}"
        print(f"  !! {msg}")
        state.setdefault("errors", []).append(msg)
        return state


# ─── System 2: Preservation Contract ──────────────────────────────────────────

def contract_node(state: CouncilState) -> CouncilState:
    print("\n--- System 2: Preservation Contract ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    try:
        from careerloop.council.safe_model import safe_construct
        resume = safe_construct(CanonicalResume, state["canonical_resume"])
        resume.sections = [
            safe_construct(ResumeSection, s)
            for s in state["canonical_resume"]["sections"]
        ]
        contract = ResumeCompiler.build_contract(resume, state["profile"])
        return {**state, "preservation_contract": contract.to_dict()}
    except Exception as e:
        msg = f"Preservation Contract failed: {e}"
        print(f"  !! {msg}")
        state.setdefault("errors", []).append(msg)
        return state


# ─── System 3: Company Intelligence ───────────────────────────────────────────


def company_intelligence_node(state: CouncilState) -> CouncilState:
    print("\n--- System 3: Company Intelligence ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state

    jd = state['jd_text']
    company = state['company']
    job_url = state.get('job_url', '')

    # Hard skip: set CAREERLOOP_SKIP_S3=1 to bypass entirely.
    if os.getenv("CAREERLOOP_SKIP_S3", "").lower() in {"1", "true", "yes"}:
        print("  → S3 SKIPPED (CAREERLOOP_SKIP_S3=1) — using JD-only stub")
        from careerloop.company_intel import _build_jd_only_result, _extract_jd_signals
        jd_signals = _extract_jd_signals(jd) if jd else {}
        ci = _build_jd_only_result(
            company=company, role_title=state.get("job_title", ""),
            jd_text=jd, jd_signals=jd_signals, web_sources=[],
            job_url=job_url, grounding_status="JD_ONLY", max_conf=0.45,
        )
        print(f"  → JD-only stub | conf={ci.confidence}")
        return {**state, "company_intelligence": ci.to_dict()}

    # Use the real Company Intelligence engine
    from careerloop.company_intel import get_or_build_company_intelligence
    
    force_refresh = os.getenv("CAREERLOOP_FORCE_REFRESH_S3", "").lower() in {"1", "true", "yes"}

    # Build candidate context from profile if available
    candidate_context = None
    profile = state.get("profile") or {}
    if profile:
        candidate_context = {
            "target_roles": profile.get("target_roles", []),
            "deal_breakers": profile.get("deal_breakers", []),
            "narrative": profile.get("narrative", ""),
        }

    # Create LLM client for synthesis (writer model — faster, cheaper, sufficient for structured extraction)
    llm = CouncilLLMClient("writer")

    ci = get_or_build_company_intelligence(
        company=company,
        role_title=state.get("job_title", ""),
        jd_text=jd,
        job_url=job_url or None,
        candidate_context=candidate_context,
        llm_client=llm,
        force_refresh=force_refresh
    )

    print(
        f"  → {ci.company_summary[:80]}... | "
        f"grounding={ci.grounding_status} | "
        f"conf={ci.confidence} | "
        f"ttl={ci.ttl_days}d"
    )
    if ci.unknowns:
        print(f"  → Unknowns: {', '.join(ci.unknowns[:3])}")

    return {**state, "company_intelligence": ci.to_dict()}


# ─── System 4: Role Decoder ───────────────────────────────────────────────────

_S4_SYSTEM = """You are a master role decoder. Extract what the job actually wants from the JD.
Separate must-haves from nice-to-haves. Identify hidden expectations.
Output JSON matching the example format below.

EXAMPLE JSON OUTPUT:
{
  "normalized_title": "AI Product Engineer",
  "seniority": "mid-senior",
  "must_haves": ["Python", "LLM API experience", "SQL", "frontend skills"],
  "nice_to_haves": ["retail/e-commerce experience", "IIT/BITS/NIT"],
  "hidden_expectations": ["CEO-facing communication", "business-outcome thinking"],
  "day_one_deliverables": ["Customer personalization intelligence layer"],
  "screening_keywords": ["AI-native", "clienteling", "business intelligence"],
  "disqualifiers": ["no LLM experience", "no coding skills"],
  "confidence": 0.85
}"""


def role_decode_node(state: CouncilState) -> CouncilState:
    print("\n--- System 4: Role Decoder ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    prompt = (
        f"JD: {state['jd_text']}\n"
        f"Company Context: {json.dumps(state['company_intelligence'])}"
    )
    result = _call(_S4_SYSTEM, prompt, label="S4 role decode", model_kind="strategy")
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    payload = result.payload
    vresult = validate_payload("role_decode", payload)
    if not vresult.ok:
        for err in vresult.errors:
            print(f"  !! Schema warning (role_decode): {err}")
    payload = vresult.payload
    print(
        f"  → {payload.get('normalized_title', '')} | "
        f"{payload.get('seniority', '')[:80]}"
    )
    return {**state, "role_decode": payload}


# ─── System 5: User Truth ─────────────────────────────────────────────────────

_S5_SYSTEM = """You are a rigorous auditor. Build a truthful evidence map in JSON.
Map candidate's experience to role requirements. Calculate seniority accurately.
Seniority is locked based on the earliest professional date in the resume.
Today is {today}.

EXAMPLE JSON OUTPUT:
{{
  "total_years_experience": 4.5,
  "confirmed_skills": [{{"skill": "Python", "years": 4, "evidence": "Built production AI systems"}}],
  "weak_skills": ["Kubernetes"],
  "evidence_bank": {{"Python": ["Built AI quality management system", "Multi-agent orchestration"]}},
  "strongest_proof_points": ["Shipped AI that automates enterprise workflows"],
  "claims_allowed": ["4+ years Python", "LLM API experience", "Agent architectures"],
  "claims_not_allowed": ["10 years AI experience", "Deep learning expert"]
}}"""


_S5_SCHEMA = schema_instruction("user_truth")


def user_truth_node(state: CouncilState) -> CouncilState:
    print("\n--- System 5: User Truth ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    prompt = (
        f"Resume: {json.dumps(state['canonical_resume'])}\n"
        f"Role: {json.dumps(state['role_decode'])}"
    )
    ctx = get_runtime_context()
    today = state.get("today") or ctx["current_month"]
    system = _S5_SYSTEM.format(today=today) + f"\n\n{_S5_SCHEMA}"
    result = _call(system, prompt, label="S5 user truth", model_kind="strategy")
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state

    # P0.3 + P0.5: validate schema and strip private_constraints before it propagates
    payload = result.payload
    payload.pop("private_constraints", None)
    vresult = validate_payload("user_truth", payload)
    if not vresult.ok:
        for err in vresult.errors:
            print(f"  !! Schema warning (user_truth): {err}")
    return {**state, "user_truth": vresult.payload}


# ─── System 6: Positioning Strategy ───────────────────────────────────────────

_S6_SYSTEM = """You are a senior career strategist. Your job is to answer ONE question: "Why is THIS candidate the best choice for THIS specific role at THIS specific company — not generically, but right now?"

Do NOT rewrite the resume. Decide on the application stance and narrative angle only.

MANDATORY REASONING STEPS (work through these before writing the JSON):

STEP 1 — THE ONE DIFFERENTIATOR:
Find the single insight that makes this candidate unusual for this role. Not "strong Python skills" (anyone can say that). The differentiator is the intersection: what does this candidate have that most applicants DON'T, that this company specifically needs RIGHT NOW?
Examples of a real differentiator:
  - "Only candidate who has built LLM systems at production scale AND shipped consumer products"
  - "Ran category P&L from zero at a startup AND managed 20+ supplier POs at a structured org — both sides of the job"
  - "Knows the Indian retail context from the inside, not just from a McKinsey deck"

STEP 2 — MAP PROOF POINTS TO JD REQUIREMENTS:
For each `must_have` in role_decode, identify the SPECIFIC bullet from evidence_bank that proves it.
If no bullet proves it, mark it as a GAP (do not invent or soften).

STEP 3 — THE HIRING MANAGER'S OBJECTION:
What is the most likely reason they WON'T shortlist this candidate? Name it explicitly.
Then write one sentence that pre-empts it in `narrative_angle`.

STEP 4 — TONE + STANCE:
PUSH = strong match (≥80% of must_haves proven). Lead with confidence.
CAREFUL_PUSH = good match (60-79%). Lead with the differentiator, acknowledge the gaps.
STRETCH = real gaps (40-59%). Lead with transferable evidence, be honest about growth path.
SKIP = bad fit (<40%). Say so clearly. Do not torture the positioning.

STRICT RULES:
- `proof_points_to_emphasize` MUST be direct quotes or close paraphrases from evidence_bank. No inventions.
- `things_to_downplay` must be real gaps or risks, not polite hedges.
- `narrative_angle` must name the differentiator (Step 1) explicitly.
- `one_line_positioning` must be role-specific, not a generic title.

Return JSON:
{
  "one_line_positioning": "<role-specific one-liner — names this company or this role's key need>",
  "narrative_angle": "<the differentiator + objection pre-empt in 1-2 sentences>",
  "lead_strengths": ["<proof from evidence_bank>", "<proof from evidence_bank>", "<proof from evidence_bank>"],
  "proof_points_to_emphasize": ["<verbatim or close paraphrase from evidence_bank>"],
  "things_to_downplay": ["<real gap — be specific>"],
  "tone_guidance": "<direct instruction for S7 tone — e.g. 'outcome-first, no AI jargon, use retail vocabulary'>",
  "recruiter_first_impression_target": "<what the recruiter should think after reading the first section>",
  "application_stance": "PUSH|CAREFUL_PUSH|STRETCH|SKIP",
  "hiring_manager_objection": "<the most likely reason they say no>",
  "objection_preempt": "<one sentence that neutralises it>",
  "reasoning": "<2-3 sentences: differentiator, gaps, why this stance>"
}"""


_S6_SCHEMA = schema_instruction("positioning_strategy")


def positioning_node(state: CouncilState) -> CouncilState:
    print("\n--- System 6: Positioning Strategy ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state

    # Only send public user_truth fields to LLM (never private_constraints)
    user_truth_safe = {k: v for k, v in (state.get('user_truth') or {}).items()
                       if k != 'private_constraints'}

    # Extract s6_positioning_context from company intelligence if available
    company_intel = state.get('company_intelligence') or {}
    s6_ctx = company_intel.get('s6_positioning_context', {}) if isinstance(company_intel, dict) else {}

    prompt = (
        f"Company Intelligence (structured): {json.dumps(s6_ctx)}\n"
        f"Company (full): {json.dumps(company_intel)}\n"
        f"Role: {json.dumps(state['role_decode'])}\n"
        f"User: {json.dumps(user_truth_safe)}"
    )
    system = _S6_SYSTEM + f"\n\n{_S6_SCHEMA}"
    result = _call(system, prompt, label="S6 positioning", model_kind="strategy")
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    payload = result.payload
    vresult = validate_payload("positioning_strategy", payload)
    if not vresult.ok:
        for err in vresult.errors:
            print(f"  !! Schema warning (positioning): {err}")
    return {**state, "positioning_strategy": vresult.payload}


# ─── System 7: Section Rewrites ───────────────────────────────────────────────

_S7_PER_SECTION_SYSTEM = """You are a resume tailoring engine. Your job is to rewrite ONE section so it reads like this candidate was BORN to fill the target role.

You MUST rewrite every section. "KEEP" is only acceptable for factual data (contact info, dates, degrees, language lists). For experience, profile, skills, and achievements sections, you MUST produce a REWRITE.

REWRITING RULES — follow ALL of them:

1. REFRAME every bullet to connect the candidate's work to what THIS role needs.
   - If `company_context` includes `language_to_use`, those exact phrases MUST appear in at least 2 bullets.
   - If `narrative_angle` says "outcome-driven AI engineer," every bullet must emphasize outcomes and AI.
   - If the role needs "personalization" and the candidate built "memory systems," reframe: "Designed a memory-driven personalization engine that..."

2. REORDER bullets: most role-relevant work goes first. If a bullet proves `day_one_deliverables`, it's bullet #1.

3. INJECT role-native language from `role_keywords` into bullet phrasing — not as decoration, but as the framing of what was built.
   Example: If role_keywords include "clienteling" and candidate built "user engagement tracking," rewrite as: "Built a clienteling intelligence layer that tracked user engagement..."

4. STRENGTHEN weak verbs: Built→Shipped, Worked on→Owned, Helped→Drove, Used→Deployed, Created→Architected.

5. APPLY `things_to_downplay`: de-emphasize or subordinate these into dependent clauses, never lead with them.

6. For PROFILE/SUMMARY sections: rewrite the entire paragraph to position the candidate as described in `narrative_angle`. Use `language_to_use` phrases. This is the recruiter's first impression — it must scream "perfect fit."

7. For SKILLS sections: reorder to put role-relevant skills first. Group by relevance to the target role.

HONESTY GUARDRAILS:
- NEVER invent metrics, numbers, dates, or claims. Use ONLY what is in `section_text`.
- Do NOT add claims from `claims_not_allowed`.
- No AI-slop (spearheaded, leveraged, synergy, passionate, results-driven, cutting-edge).
- Preserve all `[Text](URL)` links exactly as-is.
- Keep the exact same bullet count. Do NOT merge or drop bullets.

Return ONLY a JSON object:
{
  "section_id": "<same as input>",
  "tailored_bullets": [
    "<punchy, outcome-oriented version of bullet 1>",
    "<punchy, outcome-oriented version of bullet 2>"
  ],
  "change_type": "KEEP|REWRITE",
  "change_reason": "<one sentence on the tailoring logic>",
  "risk_level": "low|medium|high"
}
FORBIDDEN:
- Do NOT include headers (e.g. ## Experience)
- Do NOT include bullet markers (e.g. - or *)
- Do NOT include bolding wrappers (e.g. **)
- Return the raw text strings for the bullets only.
"""

_S7_SYSTEM = _S7_PER_SECTION_SYSTEM


def section_rewrites_node(state: CouncilState) -> CouncilState:
    import time as _time
    print("\n--- System 7: Section Rewrites (per-section loop) ---")
    s7_started_at = _time.monotonic()
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state

    user_truth_safe = {k: v for k, v in (state.get('user_truth') or {}).items()
                       if k != 'private_constraints'}
    strategy = state.get('positioning_strategy') or {}
    role_decode = state.get('role_decode') or {}
    contract = state.get('preservation_contract') or {}
    exclude = set(contract.get('sections_to_exclude', []))
    canonical = state.get('canonical_resume') or {}

    tone = strategy.get('tone_guidance', '')
    narrative_angle = strategy.get('narrative_angle', '')
    things_to_downplay = strategy.get('things_to_downplay', [])[:5]
    role_keywords = role_decode.get('screening_keywords', [])[:10]
    hidden_expectations = role_decode.get('hidden_expectations', [])[:5]
    day_one_deliverables = role_decode.get('day_one_deliverables', [])[:3]
    must_haves = role_decode.get('must_haves', [])[:5]
    proof_points = user_truth_safe.get('strongest_proof_points', [])[:5]
    claims_allowed = user_truth_safe.get('claims_allowed', [])
    claims_not_allowed = user_truth_safe.get('claims_not_allowed', [])

    # Extract s7_rewrite_context from company intelligence
    company_intel = state.get('company_intelligence') or {}
    s7_ctx = company_intel.get('s7_rewrite_context', {}) if isinstance(company_intel, dict) else {}

    if s7_ctx:
        print(f"  → S7 rewrite context: {s7_ctx.get('company_archetype', '?')[:60]}")
        print(f"  → S7 language to use: {s7_ctx.get('language_to_use', [])}")
        print(f"  → S7 language to avoid: {s7_ctx.get('language_to_avoid', [])}")

    rewrites: dict = {}
    # skipped maps section_id → reason string for diagnostics
    skipped: dict = {}
    # per-section timing log for 09_s7_debug.json
    section_timing: list = []

    allowed_sections = [
        s for s in canonical.get('sections', [])
        if s.get('section_id') not in exclude
           and s.get('raw_text', '').strip()
           and not _is_identity_or_contact_section(s)
    ]

    # ── Parallel execution: all sections run concurrently ─────────────────
    # Each section's LLM calls are independent — no cross-section state.
    # max_workers capped at 3 to avoid rate-limit hammering.
    # Results are collected via futures and reassembled in original order.
    worker_kwargs = dict(
        tone=tone,
        narrative_angle=narrative_angle,
        things_to_downplay=things_to_downplay,
        role_keywords=role_keywords,
        hidden_expectations=hidden_expectations,
        day_one_deliverables=day_one_deliverables,
        must_haves=must_haves,
        proof_points=proof_points,
        claims_allowed=claims_allowed,
        claims_not_allowed=claims_not_allowed,
        s7_rewrite_context=s7_ctx,
    )

    n_workers = min(3, max(1, len(allowed_sections)))
    print(f"  → Launching {n_workers} parallel S7 workers ({len(allowed_sections)} sections, model: deepseek-chat)...")

    # Map future → (section_id, start_time) so we can emit per-section debug info
    future_to_meta: dict = {}
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        for section in allowed_sections:
            t0 = _time.monotonic()
            fut = executor.submit(_rewrite_one_section, section, **worker_kwargs)
            future_to_meta[fut] = (section.get('section_id', ''), t0,
                                   len(section.get('raw_text', '')))

        for fut in as_completed(future_to_meta):
            fut_sid, fut_t0, orig_len = future_to_meta[fut]
            elapsed = round(_time.monotonic() - fut_t0, 2)
            sid_result, rewrite_dict, skip_reason = fut.result()
            if rewrite_dict is not None:
                rewrites[sid_result] = rewrite_dict
                section_timing.append({
                    "section_id": sid_result,
                    "status": "REWRITE",
                    "change_type": rewrite_dict.get("change_type", "REWRITE"),
                    "original_chars": orig_len,
                    "rewritten_chars": len(rewrite_dict.get("rewritten_text", "")),
                    "elapsed_s": elapsed,
                    "model": "deepseek-chat",
                })
            elif skip_reason is not None:
                skipped[sid_result] = skip_reason
                section_timing.append({
                    "section_id": sid_result,
                    "status": "FALLBACK",
                    "skip_reason": skip_reason,
                    "original_chars": orig_len,
                    "elapsed_s": elapsed,
                    "model": "deepseek-chat",
                })

    if skipped:
        print(f"  !! {len(skipped)}/{len(allowed_sections)} sections fell back to original:")
        for sid, reason in skipped.items():
            print(f"       {sid}: {reason}")
    total_elapsed = round(_time.monotonic() - s7_started_at, 2)
    print(f"  → Rewrote {len(rewrites)}/{len(allowed_sections)} sections in {total_elapsed}s")

    s7_debug = {
        "n_sections_total": len(allowed_sections),
        "n_rewritten": len(rewrites),
        "n_fallback": len(skipped),
        "n_workers": n_workers,
        "total_elapsed_s": total_elapsed,
        "sections": section_timing,
        "company_context_present": bool(s7_ctx),
        "role_keywords_used": role_keywords,
    }

    return {**state, "section_rewrites": {
        "rewrites": rewrites,
        "forbidden_edits": list(exclude),
        "skipped": list(skipped.keys()),
        "skipped_reasons": skipped,
    }, "s7_debug": s7_debug}


# ─── System 7.5: Truth Guard ──────────────────────────────────────────────────

def truth_guard_node(state: CouncilState) -> CouncilState:
    print("\n--- System 7.5: Truth Guard ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state

    from careerloop.council.truth_guard import TruthGuard

    guard = TruthGuard()
    rewrites = state.get("section_rewrites", {})
    user_truth = state.get("user_truth", {})
    evidence_bank = user_truth.get("evidence_bank", {}) if user_truth else {}
    claims_not_allowed = (
        user_truth.get("claims_not_allowed", []) if user_truth else []
    )
    cv_tenure_years = state.get("cv_tenure_years")  # B9: CV-verified tenure ceiling
    if cv_tenure_years is not None:
        print(f"  → Using cv_tenure_years={cv_tenure_years} as year-claim ceiling")
    errors = state.get("errors", [])
    all_claims = []

    if rewrites and "rewrites" in rewrites:
        for section_id, rewrite in rewrites["rewrites"].items():
            text = rewrite.get("rewritten_text", "")

            # Validate every claim in the text (B9: pass cv_tenure_years ceiling)
            claims = guard.validate(
                text, user_truth, evidence_bank, claims_not_allowed,
                cv_verified_years=cv_tenure_years,
            )
            all_claims.extend(claims)

            # Only repair if there are issues beyond VERIFIED/WEAK
            flagged = [
                c for c in claims
                if c.risk_level in ("EXAGGERATED", "FABRICATED")
            ]
            if flagged:
                repaired = guard.repair(text, claims)
                rewrites["rewrites"][section_id]["rewritten_text"] = repaired
                print(
                    f"  → Truth Guard repaired {section_id}: "
                    f"{len(flagged)} claims flagged"
                )

            # Log issues at EXAGGERATED and FABRICATED level — warn, don't block pipeline
            for claim in claims:
                if claim.risk_level in ("EXAGGERATED", "FABRICATED"):
                    msg = (
                        f"Truth Guard [{claim.risk_level}]: "
                        f"'{claim.text[:60]}...' → "
                        f"{claim.repair_suggestion or 'minimized'}"
                    )
                    state.setdefault("warnings", []).append(msg)
                    print(f"  ⚠️ {msg}")

    state.setdefault("truth_guard_flags", []).extend(all_claims)
    report = guard.generate_report(all_claims)
    verified_pct = (
        (report.verified / max(1, report.total_claims)) * 100
    )
    print(
        f"  → Truth Guard report: {report.total_claims} claims — "
        f"{report.verified} verified ({verified_pct:.0f}%), "
        f"{report.weak} weak, {report.unsupported} unsupported, "
        f"{report.exaggerated} exaggerated, {report.fabricated} fabricated"
    )

    import dataclasses
    report_dict = dataclasses.asdict(report)

    return {
        **state,
        "section_rewrites": rewrites,
        "errors": errors,
        "truth_guard_report": report_dict,
    }


# ─── System 8: Safe Assembler ─────────────────────────────────────────────────

_COVER_NOTE_SYSTEM = """Write a 3-sentence cover note that compels a recruiter to interview. Lead with a concrete achievement from the candidate's strongest proof points — not "I am writing". Be specific. Use only confirmed experience from the proof points provided.

Use the candidate's actual role, company, and metrics from the input — never invent or recycle example names.

Return JSON with this exact shape:
{"cover_note": "<3-sentence cover note tailored to the specific role and company in the input>"}"""

_RECRUITER_DM_SYSTEM = """Write a 2-sentence LinkedIn DM to a recruiter in JSON.
One sentence on the role, one sentence on why the candidate fits. Under 250 chars. No fluff, no "I'm excited to apply".

If a recruiter name is provided in `recruiter_info`, use it (e.g. "Hi [Name], ...").
Use the candidate's actual proof points from the input — never invent or recycle example names.

Return JSON with this exact shape:
{"recruiter_message": "<2-sentence DM tailored to the specific role in the input>"}"""


def assembly_node(state: CouncilState) -> CouncilState:
    print("\n--- System 8: Safe Assembler ---")

    # If errors accumulated from upstream nodes, refuse assembly
    if _has_errors(state):
        print(
            f"  !! REFUSING assembly — {len(state['errors'])} error(s) from "
            f"upstream nodes. Writing failure report."
        )
        ctx = get_runtime_context()
        failure_report = (
            f"# Resume Council Failure Report\n\n"
            f"**Generated:** {ctx['current_datetime']}\n"
            f"**Job:** {state['job_title']} at {state['company']}\n\n"
            f"## Errors ({len(state['errors'])})\n\n"
        )
        for i, err in enumerate(state["errors"], 1):
            failure_report += f"{i}. {err}\n"
        failure_report += (
            "\n## Next Steps\n\n"
            "1. Fix the underlying issue (API key, model config, input data).\n"
            "2. Re-run the council for this job.\n"
        )
        pack = ApplicationPack(
            resume_markdown="",
            cover_note="",
            recruiter_message="",
            quality_report=None,
            user_review_summary=(
                f"FAILURE: Council stopped with {len(state['errors'])} error(s). "
                f"See failure_report.md in output directory."
            ),
        )
        pack_dict = pack.to_dict()
        pack_dict["failure_report"] = failure_report
        return {**state, "application_pack": pack_dict}

    try:
        # Reconstruct objects (safe — handles LLM extra/missing keys)
        from careerloop.council.safe_model import safe_construct

        resume = safe_construct(CanonicalResume, state["canonical_resume"])
        resume.sections = [
            safe_construct(ResumeSection, s)
            for s in state["canonical_resume"]["sections"]
        ]

        rewrites_data = state["section_rewrites"].get("rewrites", {})
        from careerloop.council.safe_model import safe_construct
        rewrites = SectionRewrites(
            rewrites={k: safe_construct(SectionRewrite, v) for k, v in rewrites_data.items()}
        )

        contract = safe_construct(PreservationContract, state["preservation_contract"])

        # Deterministic assembly (no LLM)
        final_resume = ResumeCompiler.assemble(resume, rewrites, contract)

        # Build rich context for cover note + recruiter DM
        company_intel = state.get("company_intelligence", {})
        user_truth = state.get("user_truth", {})
        top_proofs = user_truth.get("strongest_proof_points", [])[:3]
        user_prompt_parts = [
            f"Role: {state['job_title']}",
            f"Company: {state['company']}",
            f"Positioning Strategy: {json.dumps(state['positioning_strategy'])}",
        ]
        if top_proofs:
            user_prompt_parts.append(f"Strongest Proof Points: {json.dumps(top_proofs)}")
        
        user_prompt = "\n".join(user_prompt_parts)

        cover_result = _call(_COVER_NOTE_SYSTEM, user_prompt, label="S8 cover note", model_kind="writer")
        cover_note = (
            cover_result.payload.get("cover_note", "")
            if cover_result.success
            else ""
        )

        # Recruiter DM gets specific recruiter info
        recruiter_info = company_intel.get("recruiter_info", {})
        dm_prompt = user_prompt
        if recruiter_info:
            dm_prompt += f"\nRecruiter Info: {json.dumps(recruiter_info)}"

        dm_result = _call(_RECRUITER_DM_SYSTEM, dm_prompt, label="S8 recruiter DM", model_kind="writer")
        recruiter_message = (
            dm_result.payload.get("recruiter_message", "")
            if dm_result.success
            else ""
        )

        claims_not_allowed = (
            user_truth.get("claims_not_allowed", []) if user_truth else []
        )

        # ─── Humanizer: Anti-AI detection + human normalization ──────────
        company_intel = state.get("company_intelligence", {})
        company_type = (
            company_intel.get("company_maturity")
            or company_intel.get("maturity")
            or "default"
        ) if company_intel else "default"

        humanizer = Humanizer(llm_client=CouncilLLMClient("writer"))

        resume_result = humanizer.humanize(
            final_resume, mode="resume",
            context={"company_type": company_type},
        )
        cover_result = humanizer.humanize(
            cover_note, mode="cover_note",
            context={"company_type": company_type},
        )
        dm_result_h = humanizer.humanize(
            recruiter_message, mode="recruiter_message",
            context={"company_type": company_type},
        )

        print(
            f"  → Humanizer (resume): {resume_result.changes_made} slop flags, "
            f"{len(resume_result.recruiter_concerns)} realism concerns"
        )
        print(
            f"  → Humanizer (cover): {cover_result.changes_made} slop flags, "
            f"{len(cover_result.recruiter_concerns)} realism concerns"
        )
        print(
            f"  → Humanizer (DM):   {dm_result_h.changes_made} slop flags, "
            f"{len(dm_result_h.recruiter_concerns)} realism concerns"
        )

        # ─── Post-Humanizer verification: check for surviving slop ────────
        _leftover_slop = 0
        for word in [
            "agentic", "multi-agent", "autonomous", "swarm",
            "AI revolution", "leverage", "spearheaded",
        ]:
            for label, text in [
                ("resume", resume_result.humanized_text),
                ("cover", cover_result.humanized_text),
                ("dm", dm_result_h.humanized_text),
            ]:
                count = text.lower().count(word.lower())
                if count > 0:
                    _leftover_slop += count
                    if count > 2 or word == "agentic":
                        print(f"  !! VERIFY: '{word}' survived Humanizer in {label} ({count}x)")
        if _leftover_slop == 0:
            print(f"  → Post-Humanizer verify: 0 surviving slop terms")
        else:
            print(f"  → Post-Humanizer verify: {_leftover_slop} surviving slop occurrences — review output manually")

        # Link preservation audit (on humanized output — the actual deliverable)
        link_audit = ResumeCompiler._verify_links_preserved(
            resume, resume_result.humanized_text, contract
        )
        preserved_links = ResumeCompiler.extract_links_from_text(
            resume_result.humanized_text
        )

        # Log warnings from link audit
        for warning in link_audit.warnings:
            print(f"  !! {warning}")

        # ─── Sections-not-tailored visibility ────────────────────────────
        # Identify which allowed sections got NO rewrite (fell back to original).
        # These sections are in the final resume but were NOT touched by S7.
        rewrites_data = state.get("section_rewrites", {}).get("rewrites", {})
        skipped_sids = state.get("section_rewrites", {}).get("skipped", [])
        allowed_sids = {s.get("section_id") for s in (state.get("canonical_resume") or {}).get("sections", [])
                        if s.get("section_id") not in contract.sections_to_exclude
                        and not _is_identity_or_contact_section(s)}
        rewritten_sids = set(rewrites_data.keys())
        fallback_sids = sorted(allowed_sids - rewritten_sids)

        if fallback_sids:
            print(f"\n  !! WARNING — {len(fallback_sids)} section(s) fell back to ORIGINAL (not tailored):")
            for fid in fallback_sids:
                reason = state.get("section_rewrites", {}).get("skipped_reasons", {}).get(fid, "unknown")
                print(f"       {fid}: {reason}")
        else:
            print(f"  → All {len(rewritten_sids)} allowed sections were rewritten — no fallbacks")

        quality_report = ResumeCompiler.generate_quality_report(
            resume, rewrites, contract, claims_not_allowed
        )

        pack = ApplicationPack(
            resume_markdown=resume_result.humanized_text,
            cover_note=cover_result.humanized_text,
            recruiter_message=dm_result_h.humanized_text,
            quality_report=quality_report,
            preserved_links=preserved_links,
            link_audit=link_audit,
            user_review_summary=(
                f"Check your new resume. "
                f"{len(rewritten_sids)}/{len(rewritten_sids)+len(fallback_sids)} sections rewritten. "
                + (f"⚠️ {len(fallback_sids)} fell back to original: {', '.join(fallback_sids)}" if fallback_sids else "✅ All sections tailored.")
            ),
        )

        # Save pre-humanizer text + humanizer report for visibility
        humanizer_report = {
            "resume": {
                "slop_flags": len(resume_result.flags),
                "changed_lines": resume_result.changes_made,
                "realism_concerns": len(resume_result.recruiter_concerns),
                "recruiter_concerns": resume_result.recruiter_concerns,
            },
            "cover_note": {
                "slop_flags": len(cover_result.flags),
                "changed_lines": cover_result.changes_made,
                "realism_concerns": len(cover_result.recruiter_concerns),
            },
            "recruiter_message": {
                "slop_flags": len(dm_result_h.flags),
                "changed_lines": dm_result_h.changes_made,
                "realism_concerns": len(dm_result_h.recruiter_concerns),
            },
        }

        return {
            **state,
            "application_pack": pack.to_dict(),
            "pre_humanizer_resume": final_resume,
            "humanizer_output": resume_result.humanized_text,  # post-humanizer (actual deliverable)
            "humanizer_report": humanizer_report,
        }

    except Exception as e:
        msg = f"Safe Assembler failed: {e}"
        print(f"  !! {msg}")
        state.setdefault("errors", []).append(msg)
        ctx = get_runtime_context()
        failure_report = (
            f"# Resume Council Failure Report\n\n"
            f"**Generated:** {ctx['current_datetime']}\n"
            f"**Job:** {state['job_title']} at {state['company']}\n\n"
            f"## Fatal Error\n\n{msg}\n"
        )
        pack = ApplicationPack(
            resume_markdown="",
            cover_note="",
            recruiter_message="",
            quality_report=None,
            user_review_summary=f"FAILURE: Assembly error — {msg}",
        )
        pack_dict = pack.to_dict()
        pack_dict["failure_report"] = failure_report
        return {**state, "application_pack": pack_dict}


# ─── Build & Compile Graph ─────────────────────────────────────────────────────


def build_council_graph():
    g = StateGraph(CouncilState)

    g.add_node("parse", parse_node)
    g.add_node("contract", contract_node)
    g.add_node("intelligence", company_intelligence_node)
    g.add_node("decode", role_decode_node)
    g.add_node("truth", user_truth_node)
    g.add_node("strategy", positioning_node)
    g.add_node("rewrites", section_rewrites_node)
    g.add_node("truth_guard", truth_guard_node)
    g.add_node("assembly", assembly_node)

    g.set_entry_point("parse")
    g.add_edge("parse", "contract")
    g.add_edge("contract", "intelligence")
    g.add_edge("intelligence", "decode")
    g.add_edge("decode", "truth")
    g.add_edge("truth", "strategy")
    g.add_edge("strategy", "rewrites")
    g.add_edge("rewrites", "truth_guard")
    g.add_edge("truth_guard", "assembly")
    g.add_edge("assembly", END)

    return g.compile()


_GRAPH = None


def get_council_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_council_graph()
    return _GRAPH
