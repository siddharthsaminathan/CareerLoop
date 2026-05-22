"""
Resume Normalizer — Council Markdown → NormalizedResume.

This is the SINGLE normalization point. Every template renderer consumes
NormalizedResume, never raw markdown.

Handles two input formats:
  1. Council flat ## output (all sections at ## level)
  2. Original cv.md (### sub-headings inside Work Experience)

Has NO dependency on the Council, Humanizer, or any external library.
Uses only Python standard library.
"""

import re
from typing import List, Optional, Tuple

from careerloop.rendering.resume_model import (
    NormalizedResume,
    HeaderInfo,
    SkillRow,
    ExperienceEntry,
    EducationEntry,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Section heading patterns (lowercase, normalized)
SECTION_PATTERNS = {
    "profile":       re.compile(r"^(profile|summary|about\s*me|about)$"),
    "contact":       re.compile(r"^(contact|contact\s*info|contact\s*information)$"),
    "education":     re.compile(r"^(education|academic|academics|academic\s*background)$"),
    "skills":        re.compile(r"^(skills|technical\s*skills|competencies|technologies|core\s*competencies)$"),
    "languages":     re.compile(r"^(languages?)$"),
    "work_experience": re.compile(r"^(work\s*experience|professional\s*experience|experience|employment)$"),
    "achievements":  re.compile(r"^(key\s*achievements?|achievements?|highlights|accomplishments?|key\s*accomplishments?)$"),
    "thesis":        re.compile(r"^(master'?s?\s*thesis|thesis|dissertation|research|research\s*work)$"),
    "projects":      re.compile(r"^(projects?|key\s*projects?|portfolio)$"),
    "certifications": re.compile(r"^(certifications?|certificates?|licenses?)$"),
}

# Sections that should never appear in the normalized resume
FORBIDDEN_KEYWORDS = [
    "deal-breaker", "deal breaker", "deal_breaker",
    "target role", "target_role",
    "internal note", "internal_note",
    "fit score", "fit_score",
    "council verdict", "council_verdict",
    "warnings",
    "prompt note", "prompt_note",
    "search preference", "search_preference",
    "outreach preference", "outreach_preference",
    "salary", "salary expectation", "salary_expectation",
    "private", "strategy metadata", "strategy_metadata",
    "preference", "constraint",
]

# Role heading pattern: detects "Role — Company, Location (Dates)"
ROLE_HEADING_RE = re.compile(
    r"^(?P<role>.+?)\s+[—\-–]\s+(?P<rest>.+)$"
)
DATES_RE = re.compile(r"\(([^)]+)\)\s*$")

# Collapsed bullet split pattern: "sentence. - Next sentence"
# Matches period + dash/hyphen + capital letter = inter-bullet boundary
COLLAPSED_BULLET_RE = re.compile(r"\.\s+[-–—]\s+(?=[A-Z])")

# Fallback: dash + capital letter (no period required, wider pattern)
COLLAPSED_BULLET_FALLBACK_RE = re.compile(r"\s+[-–—]\s+(?=[A-Z])")


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def normalize(md_text: str) -> NormalizedResume:
    """Parse Council markdown output into a structured NormalizedResume.

    This is the SINGLE normalization point. Every template renderer
    consumes NormalizedResume, never raw markdown.

    Args:
        md_text: Raw markdown from Council output or original cv.md.

    Returns:
        Fully parsed and normalized resume data model.
    """
    md_text = _fix_encoding_artifacts(md_text)
    md_text = _prepare_plaintext_resume(md_text)
    blocks = _split_into_blocks(md_text)
    classified = _classify_blocks(blocks)

    header = _parse_header(classified)
    profile = _parse_profile(classified)
    skills = _parse_skills(classified)
    experience = _parse_experience(classified)
    achievements = _parse_achievements(classified)
    projects = _parse_projects(classified)
    education = _parse_education(classified)
    thesis = _parse_thesis(classified)
    languages = _parse_languages(classified)

    # ── Post-normalization validation ──────────────────────────────────────
    _validate_normalized(header, skills, experience, education, achievements, md_text)

    return NormalizedResume(
        header=header,
        profile=profile,
        skills=skills,
        experience=experience,
        achievements=achievements,
        projects=projects,
        education=education,
        thesis=thesis,
        languages=languages,
    )


def _validate_normalized(header, skills, experience, education, achievements, md_text):
    """Validate normalized resume completeness. Logs warnings, never blocks."""
    issues = []
    
    if not header or not header.name:
        issues.append("Name missing from header")
    if not skills:
        issues.append("Skills section empty — no skills parsed from resume")
    if not experience:
        issues.append("Experience section empty — no work entries parsed")
    if not education:
        issues.append("Education section empty — no education entries parsed")
    
    # Check for empty roles in experience
    empty_roles = [e for e in experience if not e.role]
    if empty_roles:
        companies = [e.company for e in empty_roles]
        issues.append(f"Missing role title for: {', '.join(companies)}")
    
    # Check skills have items
    empty_skill_rows = [s for s in skills if not s.items]
    if empty_skill_rows:
        labels = [s.label for s in empty_skill_rows]
        issues.append(f"Empty skill rows: {', '.join(labels)}")
    
    if issues:
        print("  ⚠ Normalizer validation warnings:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  ✓ Normalizer validation passed")


# ═══════════════════════════════════════════════════════════════════════════════
# Encoding Artifact Fixes
# ═══════════════════════════════════════════════════════════════════════════════

def _make_encoding_fixes():
    return [
        ("\u00e2\u20ac\u201c", "\u2014"),  # â€" → em dash
        ("\u00e2\u20ac\u201d", "\u2013"),  # â€" → en dash variant
        ("\u00e2\u20ac\u2122", "\u2019"),  # â€™ → right single quote
        ("\u00e2\u20ac\u02dc", "\u2018"),  # â€˜ → left single quote
        ("\u00e2\u20ac\u0153", "\u201c"),  # â€œ → left double quote
        ("\u00e2\u20ac\u009d", "\u201d"),  # â€ → right double quote
        ("\u00e2\u2020\u2019", "\u2192"),  # â†' → right arrow
        ("\u00e2\u2020\u201c", "\u2190"),  # â†" → left arrow
        ("\u00c3\u00a9", "\u00e9"),        # Ã© → é
        ("\u00c3\u00a0", "\u00e0"),        # Ã  → à
        ("\u00c3\u00b6", "\u00f6"),        # Ã¶ → ö
        ("\u00c3\u00bc", "\u00fc"),        # Ã¼ → ü
        ("\u00c3\u00a4", "\u00e4"),        # Ã¤ → ä
        ("\u00c3\u00b8", "\u00f8"),        # Ã¸ → ø
        ("\u00c3\u00a5", "\u00e5"),        # Ã¥ → å
    ]

_ENCODING_FIXES = _make_encoding_fixes()


def _fix_encoding_artifacts(text: str) -> str:
    """Fix common Windows-1252 / Latin-1 mis-encoding artifacts in markdown text."""
    for bad, good in _ENCODING_FIXES:
        text = text.replace(bad, good)
    return text


def _prepare_plaintext_resume(text: str) -> str:
    """Repair common PDF/plaintext resume extraction before block splitting."""
    if not text or re.search(r"^#{1,6}\s+\S", text, re.MULTILINE):
        return text

    headers = [
        "PROFESSIONAL EXPERIENCE", "WORK EXPERIENCE", "EXPERIENCE",
        "SUMMARY", "PROFILE", "EDUCATION", "SKILLS", "PROJECTS",
        "ACHIEVEMENTS", "CERTIFICATIONS", "LANGUAGES",
    ]
    combined = "|".join(re.escape(h) for h in headers)
    text = re.sub(r"(?m)^(" + combined + r")\s*$", r"\n\n## \1\n\n", text)
    text = re.sub(r"[\u2022\u25CF\u25B8\u25B6\u25C6\u25E6\u2219]", "\n- ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# Block Splitting
# ═══════════════════════════════════════════════════════════════════════════════

def _split_into_blocks(md_text: str) -> List[Tuple[str, str, str]]:
    """Split markdown into (heading_raw, heading_clean, body) triples at ## level.

    Returns list of (heading_line, normalized_heading, body) where:
      - heading_line: raw heading text including '## ' prefix
      - normalized_heading: heading text lowercased, stripped, no '## '
      - body: all text between this heading and the next
    """
    # Normalize line endings
    text = md_text.replace("\r\n", "\n").replace("\r", "\n")

    # Prepend newline so the first heading matches the split pattern
    text = "\n" + text

    blocks: List[Tuple[str, str, str]] = []

    # Extract level-1 heading if present (only the first one)
    l1_match = re.match(r"\n# ([^\n]+)\n?", text)
    if l1_match:
        l1_heading = l1_match.group(1).strip()
        # Remove the L1 heading from text for L2 splitting
        text = text[l1_match.end():]
        l1_norm = _normalize_heading(l1_heading)
        if not _is_forbidden(l1_norm):
            blocks.append((f"## {l1_heading}", l1_norm, ""))

    # Split on newline followed by ## (but not ###)
    raw_blocks = re.split(r"\n(?=## )", text)
    raw_blocks = [b for b in raw_blocks if b.strip()]

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        if not block.startswith("## "):
            preamble = block.strip()
            if preamble:
                blocks.append(("## Contact", "contact", preamble))
            continue

        # Split into heading line and body
        newline_idx = block.find("\n")
        if newline_idx == -1:
            heading_line = block
            body = ""
        else:
            heading_line = block[:newline_idx].strip()
            body = block[newline_idx + 1:].strip()

        heading_clean = heading_line[3:].strip()  # remove "## "
        heading_normalized = _normalize_heading(heading_clean)

        # Skip forbidden sections
        if _is_forbidden(heading_normalized):
            continue

        blocks.append((heading_line, heading_normalized, body))

    return blocks


def _normalize_heading(heading: str) -> str:
    """Normalize a heading for comparison: lowercase, collapse whitespace,
    remove special chars except spaces and hyphens."""
    h = heading.lower().strip()
    h = re.sub(r"[^a-z0-9\s\-]", "", h)
    h = re.sub(r"\s+", " ", h).strip()
    return h


def _is_forbidden(heading_normalized: str) -> bool:
    """Check if a section heading contains forbidden keywords."""
    h = heading_normalized.replace(" ", "_")
    for keyword in FORBIDDEN_KEYWORDS:
        kw_normalized = keyword.replace(" ", "_")
        if kw_normalized in h or kw_normalized in heading_normalized:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Block Classification
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_blocks(
    blocks: List[Tuple[str, str, str]]
) -> dict:
    """Classify each block into a section type.

    Returns dict with keys: 'name', 'profile', 'contact', 'education',
    'skills', 'languages', 'work_experience', 'role_blocks', 'achievements',
    'thesis', 'projects', 'certifications', 'unknown'.

    'work_experience' block is the marker (may be empty in Council output).
    'role_blocks' are experience entry blocks detected after work_experience.
    """
    result: dict = {
        "name_block": None,
        "profile": None,
        "contact": None,
        "education": None,
        "skills": None,
        "languages": None,
        "work_experience": None,
        "role_blocks": [],
        "achievements": None,
        "thesis": None,
        "projects": None,
        "certifications": None,
        "unknown": [],
    }

    # Known section names after which roles end
    role_terminators = {
        "achievements", "thesis", "education", "skills",
        "languages", "profile", "contact", "projects", "certifications",
    }

    in_roles = False
    first_block = True

    for heading_line, heading_norm, body in blocks:
        section_type = _identify_section(heading_norm)

        # First block: if it looks like a name heading (has "cv" or no known type), treat as name
        if first_block:
            first_block = False
            if section_type is None or heading_norm in (
                "name", "header", "cv", "resume"
            ):
                # Check if this looks like a name heading
                raw_heading = heading_line[3:].strip()  # remove "## "
                if _looks_like_name_heading(raw_heading) or section_type is None:
                    result["name_block"] = (heading_line, heading_norm, body)
                    continue

        # Work Experience marker: subsequent blocks may be roles
        if section_type == "work_experience":
            result["work_experience"] = (heading_line, heading_norm, body)
            in_roles = True
            continue

        # If we're in role mode and we hit a known section terminator, exit roles
        if in_roles and section_type in role_terminators:
            in_roles = False
            # Fall through to handle this section normally

        # If we're in role mode and this looks like a role heading, add it
        if in_roles:
            raw_heading = heading_line[3:].strip()
            if _looks_like_role_heading(raw_heading):
                result["role_blocks"].append((heading_line, heading_norm, body))
                continue
            else:
                # Doesn't look like a role — exit role mode and handle normally
                in_roles = False

        # Map to result key
        if section_type:
            result[section_type] = (heading_line, heading_norm, body)
        else:
            result["unknown"].append((heading_line, heading_norm, body))

    # If no roles found via flat ##, check for ### sub-headings in work_experience body
    if not result["role_blocks"] and result["work_experience"]:
        _, _, we_body = result["work_experience"]
        if we_body and "### " in we_body:
            result["role_blocks"] = _parse_nested_roles(we_body)

    return result


def _identify_section(heading_normalized: str) -> Optional[str]:
    """Identify the section type from a normalized heading. Returns None if unknown."""
    # Check against known patterns (order matters: more specific first)
    priority_order = [
        "work_experience", "achievements", "education", "skills",
        "languages", "profile", "contact", "thesis", "projects",
        "certifications",
    ]

    for key in priority_order:
        if SECTION_PATTERNS[key].search(heading_normalized):
            return key

    return None


def _looks_like_name_heading(raw_heading: str) -> bool:
    """Check if a heading looks like a name/title heading (not a section)."""
    lower = raw_heading.lower().strip()
    # Contains "CV" or "Resume"
    if re.search(r"\bcv\b", lower) or re.search(r"\b(?:r[eé]sum[eé]|curriculum\s*vitae)\b", lower):
        return True
    # Very short headings that aren't known sections
    words = lower.split()
    if 1 <= len(words) <= 4 and not _identify_section(_normalize_heading(raw_heading)):
        return True
    return False


def _looks_like_role_heading(raw_heading: str) -> bool:
    """Check if a heading looks like a role entry (has '—' or '-' separator
    with dates in parentheses or company-like structure)."""
    # Must have an em dash or spaced hyphen separator
    if not re.search(r"\s+[—\-–]\s+", raw_heading):
        return False

    # Must have date-like parentheses at the end, OR look like "Role — Company"
    has_dates = bool(DATES_RE.search(raw_heading))
    has_separator = bool(ROLE_HEADING_RE.search(raw_heading))

    if has_dates or has_separator:
        return True

    return False


def _parse_nested_roles(we_body: str) -> List[Tuple[str, str, str]]:
    """Parse ### sub-headings inside Work Experience body (cv.md format)."""
    # Split on ### headings
    parts = re.split(r"\n(?=### )", "\n" + we_body)
    role_blocks = []
    for part in parts:
        part = part.strip()
        if not part or not part.startswith("### "):
            continue
        newline_idx = part.find("\n")
        if newline_idx == -1:
            heading_line = part
            body = ""
        else:
            heading_line = part[:newline_idx].strip()
            body = part[newline_idx + 1:].strip()

        # Convert ### to ## for consistency
        heading_line = "## " + heading_line[4:].strip()
        heading_norm = _normalize_heading(heading_line[3:])
        role_blocks.append((heading_line, heading_norm, body))
    return role_blocks


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers: Header
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_header(classified: dict) -> HeaderInfo:
    """Extract HeaderInfo from name block and contact block."""
    header = HeaderInfo()

    # Extract name from name block
    name_block = classified.get("name_block")
    if name_block:
        _, _, body = name_block
        raw_heading = name_block[0][3:].strip()  # remove "## "
        # Remove trailing "— CV", "- CV", ", CV", etc.
        name = re.sub(r"\s*[—\-–,]\s*CV\s*$", "", raw_heading, flags=re.IGNORECASE).strip()
        name = re.sub(r"\s*[—\-–,]\s*(?:R[eé]sum[eé]|Curriculum\s*Vitae)\s*$", "", name, flags=re.IGNORECASE).strip()
        header.name = name
        # Some resumes embed contact directly under the name heading.
        if body and not classified.get("contact"):
            preview = "\n".join(body.strip().splitlines()[:6])
            _parse_header_title(preview, header)
            _parse_contact_body(preview, header)

    # Extract contact details from contact block
    contact_block = classified.get("contact")
    if contact_block:
        _, _, body = contact_block
        _parse_header_title(body, header)
        _parse_contact_body(body, header)

    # If no name from block heading, try contact body
    if not header.name and contact_block:
        _, _, body = contact_block
        first_line = body.strip().split("\n")[0].strip()
        m = re.match(r"^#+\s*(.+)", first_line)
        if m:
            name = re.sub(r"\s*[—\-–,]\s*CV\s*$", "", m.group(1).strip(), flags=re.IGNORECASE).strip()
            header.name = name
        elif first_line and "@" not in first_line and not re.search(r"\d{3,}", first_line):
            header.name = _sanitize_text(_strip_markdown_formatting(first_line))

    return header


def _parse_header_title(body: str, header: HeaderInfo) -> None:
    """Capture the candidate's declared professional title from the name block."""
    if header.title:
        return

    for raw_line in body.strip().split("\n"):
        line = _sanitize_text(_strip_markdown_formatting(raw_line.strip()))
        line = line.strip(" -|")
        if not line:
            continue
        if "@" in line or re.search(r"(?:https?://|www\.|github\.com|linkedin\.com)", line, re.IGNORECASE):
            continue
        if re.search(r"\+?\d[\d\s().-]{7,}\d", line):
            continue
        if header.name and line.lower() == header.name.lower():
            continue
        roleish = re.search(
            r"\b(engineer|manager|founder|architect|developer|analyst|designer|scientist|consultant|product|systems?)\b",
            line,
            re.IGNORECASE,
        )
        if roleish and len(line) <= 90:
            header.title = line
            return


def _parse_contact_body(body: str, header: HeaderInfo) -> None:
    """Parse contact bullet list into HeaderInfo fields."""
    patterns = {
        "phone":     re.compile(r"^(?:phone|tel|mobile|cell)\b[\s:]*\*?\*?\s*(.+)", re.IGNORECASE),
        "email":     re.compile(r"^(?:email|e-mail|mail)\b[\s:]*\*?\*?\s*(.+)", re.IGNORECASE),
        "location":  re.compile(r"^(?:location|address|city|based)\b[\s:]*\*?\*?\s*(.+)", re.IGNORECASE),
        "portfolio": re.compile(r"^(?:portfolio|website|web|site|url)\b[\s:]*\*?\*?\s*(.+)", re.IGNORECASE),
        "github":    re.compile(r"^(?:github|git)\b[\s:]*\*?\*?\s*(.+)", re.IGNORECASE),
        "linkedin":  re.compile(r"^(?:linkedin|linked\s*in)\b[\s:]*\*?\*?\s*(.+)", re.IGNORECASE),
    }

    for raw_line in body.strip().split("\n"):
        raw_line = _strip_markdown_formatting(raw_line.strip())
        raw_line = re.sub(r"^\s*(?:[-*•·]\s+|\+\s+)", "", raw_line)
        if not raw_line:
            continue
        tokens = _split_contact_tokens(raw_line)
        for line in tokens:
            if not line:
                continue
            if not header.email:
                email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", line)
                if email_match:
                    header.email = _sanitize_text(email_match.group(0))
            if not header.phone:
                phone_match = re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", line)
                if phone_match:
                    header.phone = _sanitize_text(phone_match.group(0).strip())
            if not header.linkedin_url:
                linkedin_match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[^\s|,;]+", line, re.IGNORECASE)
                if linkedin_match:
                    header.linkedin_url = _sanitize_text(linkedin_match.group(0).rstrip("/"))
                    header.linkedin_display = _sanitize_text(re.sub(r"^(?:www\.)?linkedin\.com/in/", "", _url_to_display(header.linkedin_url)))
            if not header.github_url:
                github_match = re.search(r"(?:https?://)?(?:www\.)?github\.com/[^\s|,;]+", line, re.IGNORECASE)
                if github_match:
                    header.github_url = _sanitize_text(github_match.group(0).rstrip("/"))
                    header.github_display = _sanitize_text(_url_to_display(header.github_url).replace("github.com/", ""))
            if not header.portfolio_url and "@" not in line and re.search(r"(?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s|,;]*)?", line, re.IGNORECASE):
                low = line.lower()
                if "linkedin.com" not in low and "github.com" not in low:
                    url_match = re.search(r"(?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s|,;]*)?", line, re.IGNORECASE)
                    if url_match:
                        header.portfolio_url = _sanitize_text(url_match.group(0).rstrip("/"))
                        header.portfolio_display = _sanitize_text(_url_to_display(header.portfolio_url))
            if not header.location:
                is_explicit_field = False
                for other_key, other_pattern in patterns.items():
                    if other_pattern.search(line):
                        is_explicit_field = True
                        break
                # Skip: line already yielded phone/email/linkedin/github
                already_has_contact = bool(
                    (header.phone and re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", line))
                    or (header.email and re.search(r"[\w.+-]+@[\w.-]+\.\w+", line))
                )
                if already_has_contact:
                    continue
                if not is_explicit_field and (
                    "@" not in line
                    and not re.search(r"(?:https?://|www\.)", line, re.IGNORECASE)
                    and re.search(r"[A-Za-z]", line)
                    and ("," in line or len(line.split()) <= 4)
                ):
                    location_candidate = line.strip(" -|·")
                    # Avoid tagging role subtitles as location in contact preambles.
                    roleish = re.search(
                        r"\b(engineer|manager|founder|architect|developer|analyst|designer|scientist|consultant|product)\b",
                        location_candidate,
                        re.IGNORECASE,
                    )
                    looks_like_name = bool(
                        header.name
                        and location_candidate.strip().lower() == header.name.strip().lower()
                    )
                    upper_nameish = bool(
                        re.match(r"^[A-Z][A-Z\s'.-]+$", location_candidate)
                        and len(location_candidate.split()) >= 2
                    )
                    if (
                        location_candidate
                        and len(location_candidate) <= 60
                        and not roleish
                        and not looks_like_name
                        and not upper_nameish
                    ):
                        header.location = _sanitize_text(location_candidate)

            for key, pattern in patterns.items():
                if key == "phone" and header.phone:
                    continue
                if key == "email" and header.email:
                    continue
                if key == "linkedin" and header.linkedin_url:
                    continue
                if key == "github" and header.github_url:
                    continue
                if key == "portfolio" and header.portfolio_url:
                    continue
                if key == "location" and header.location:
                    continue
                m = pattern.search(line)
                if m:
                    val = _strip_markdown_formatting(m.group(1).strip())
                    val = val.rstrip(".,;")

                    if key == "phone":
                        header.phone = _sanitize_text(val)
                    elif key == "email":
                        header.email = _sanitize_text(val)
                    elif key == "location":
                        header.location = _sanitize_text(val)
                    elif key == "portfolio":
                        header.portfolio_url = _sanitize_text(val)
                        header.portfolio_display = _sanitize_text(_url_to_display(val))
                    elif key == "github":
                        header.github_url = _sanitize_text(val)
                        header.github_display = _sanitize_text(_url_to_display(val).replace("github.com/", ""))
                    elif key == "linkedin":
                        header.linkedin_url = _sanitize_text(val)
                        header.linkedin_display = _sanitize_text(re.sub(r"^(?:www\.)?linkedin\.com/in/", "", _url_to_display(val)))
                    break


def _split_contact_tokens(line: str) -> List[str]:
    # Normalize explicit labels before tokenization to reduce greedy capture.
    prepared = line.replace("•", "·").replace(" | ", "|")
    parts = re.split(r"\s*[|·]\s*", prepared)
    clean = [p.strip() for p in parts if p.strip()]
    return clean if clean else [line.strip()]


def _url_to_display(url: str) -> str:
    """Convert a URL to a display-friendly form."""
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"/$", "", url)
    return url


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers: Profile
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_profile(classified: dict) -> str:
    """Extract profile/summary text.

    Primary source: dedicated ## SUMMARY / ## PROFILE block.
    Fallback: summary paragraph embedded in the contact/preamble block
    (e.g. Hayagreev-style CVs where the summary sits right after the
    contact line with no section heading).
    """
    profile_block = classified.get("profile")
    if profile_block:
        _, _, body = profile_block
        # Remove standalone horizontal rules that sometimes leak from section joins.
        cleaned_lines = []
        for line in body.splitlines():
            if re.match(r"^\s*[-*_]{3,}\s*$", line.strip()):
                continue
            cleaned_lines.append(line)
        cleaned = "\n".join(cleaned_lines).strip()
        return _sanitize_text(cleaned)

    # Fallback: look for a summary paragraph in the contact block.
    # The preamble (before any ## heading) is stored as "contact".  For
    # CVs that embed the summary directly after the contact line, it appears
    # as a long paragraph that contains no phone/email/URL signals.
    contact_block = classified.get("contact")
    if contact_block:
        _, _, body = contact_block
        _contact_signal = re.compile(
            r"(?:@|\+?\d[\d\s().-]{6,}\d|https?://|www\.|linkedin\.com|github\.com"
            r"|T:\s*\+|E:\s*\w+@|Phone|Email|LinkedIn)",
            re.IGNORECASE,
        )
        # Pattern to detect all-caps name lines (e.g. "HAYAGREEV SIVAKUMAR", "JOHN DOE")
        _name_line = re.compile(r"^[A-Z][A-Z\s\.'-]{2,39}$")

        candidate_paras: list[str] = []
        for para in re.split(r"\n{2,}", body):
            para = para.strip()
            if not para:
                continue
            # Skip paragraphs that are purely contact/link lines
            lines = [l.strip() for l in para.splitlines() if l.strip()]
            content_lines = [l for l in lines if not _contact_signal.search(l)]
            if not content_lines:
                continue
            # Strip leading all-caps name lines (e.g. "HAYAGREEV SIVAKUMAR")
            content_lines = [
                l for l in content_lines
                if not _name_line.match(l)
            ]
            if not content_lines:
                continue
            # Must be a real sentence (>60 chars, not a header-only line)
            candidate = " ".join(content_lines).strip()
            if len(candidate) > 60:
                candidate_paras.append(candidate)
        if candidate_paras:
            return _sanitize_text(" ".join(candidate_paras))

    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers: Skills
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_skills(classified: dict) -> List[SkillRow]:
    """Parse skills table into SkillRow list."""
    skills_block = classified.get("skills")
    if not skills_block:
        return []

    _, _, body = skills_block
    if not body:
        return []

    # Try table parsing first
    if "|" in body:
        rows = _parse_markdown_table(body)
        if rows:
            return rows

    # Fallback: bullet list (each bullet = one skill row with label: items)
    return _parse_skills_from_bullets(body)


def _parse_markdown_table(table_text: str) -> List[SkillRow]:
    """Parse a markdown table into SkillRow list.

    Table format:
        | Category | Technologies |
        |----------|-------------|
        | **AI Systems** | LLM APIs, RAG, ... |

    Also handles Council's collapsed || row separator format
    where all rows are concatenated on one line.
    """
    # Fix Council output: collapsed rows with || separator
    # "| a | b || c | d |" → "| a | b |\n| c | d |"
    if "||" in table_text:
        table_text = re.sub(r"\|\|", "|\n|", table_text)

    lines = table_text.strip().split("\n")
    rows: List[SkillRow] = []

    for line in lines:
        line = line.strip()
        # Fix trailing punctuation after final pipe: "| text |." → "| text |"
        line = re.sub(r'\|\s*[.,;:]\s*$', '|', line)
        if not line.startswith("|") or not line.endswith("|"):
            # Handle malformed ending
            line = re.sub(r'[.,;:]\s*$', '', line)
            if not line.startswith("|"):
                continue

        # Split by pipe and clean cells
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]  # remove empty strings from start/end splits

        # Skip separator rows (e.g., |---|----| or |:---|:---|)
        if all(re.match(r"^[-: ]+$", c) for c in cells if c):
            continue

        # Skip header rows (contain "Category", "Technologies", etc.)
        if any(c.lower() in ("category", "categories", "technologies", "skills", "skill")
               for c in cells if c):
            continue

        if len(cells) >= 2:
            label = _sanitize_text(_strip_markdown_formatting(cells[0]))
            items_str = _strip_markdown_formatting(" | ".join(cells[1:]))

            # Split items string into individual items
            items = [_sanitize_text(i) for i in _split_skill_items(items_str)]
            rows.append(SkillRow(label=label, items=items))

    return rows


def _split_skill_items(items_str: str) -> List[str]:
    """Split a comma-separated skill items string into individual items."""
    if not items_str:
        return []

    # Split by comma, but be careful with parenthetical groups
    # "LLM APIs, RAG pipelines, embeddings" → ["LLM APIs", "RAG pipelines", "embeddings"]
    # "Redis (caching, queues), PostgreSQL" → ["Redis (caching, queues)", "PostgreSQL"]
    items: List[str] = []
    current: List[str] = []
    paren_depth = 0

    for char in items_str:
        if char == "," and paren_depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
        else:
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
            current.append(char)

    # Last item
    item = "".join(current).strip()
    if item:
        items.append(item)

    return items


def _parse_skills_from_bullets(body: str) -> List[SkillRow]:
    """Parse skills from bullet list format.

    Format:
        - **Category:** item1, item2, item3
        - Category: item1, item2
    """
    rows: List[SkillRow] = []
    lines = body.strip().split("\n")
    current_label: Optional[str] = None
    current_items: List[str] = []

    def flush_group() -> None:
        nonlocal current_label, current_items
        if current_label and current_items:
            rows.append(SkillRow(label=current_label, items=current_items))
        current_label = None
        current_items = []

    for line in lines:
        line = line.strip()
        heading_match = re.match(r"^\*\*(.+?)\*\*\s*$", line)
        if heading_match:
            flush_group()
            current_label = _sanitize_text(heading_match.group(1).strip())
            continue

        # Strip bullet marker
        is_bullet = bool(re.match(r"^\s*[-*+]\s*", line))
        line = re.sub(r"^\s*[-*+]\s*", "", line)
        if not line:
            continue

        # Try "Category: items" or "**Category:** items"
        m = re.match(r"^(?:\*\*)?(.+?)(?:\*\*)?\s*:\s*(.+)$", line)
        if m:
            flush_group()
            label = _sanitize_text(_strip_markdown_formatting(m.group(1).strip()))
            items_str = _strip_markdown_formatting(m.group(2).strip())
            current_label = label
            current_items = [_sanitize_text(i) for i in _split_skill_items(items_str)]
        elif current_label and is_bullet:
            current_items.append(_sanitize_text(_strip_markdown_formatting(line)))

    flush_group()
    
    # Fallback: no colon-separated categories found — treat each bullet as a compact skill row
    # Format: "- Python, SQL, Airflow - deployed for data pipelines"
    if not rows:
        flat_items: List[str] = []
        for line in lines:
            line = line.strip()
            line = re.sub(r"^\s*[-*+]\s*", "", line)
            if not line:
                continue
            flat_items.append(_sanitize_text(_strip_markdown_formatting(line)))
        if flat_items:
            rows.append(SkillRow(label="", items=flat_items))

    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers: Experience
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_experience(classified: dict) -> List[ExperienceEntry]:
    """Parse work experience blocks into ExperienceEntry list."""
    role_blocks = classified.get("role_blocks", [])
    if not role_blocks:
        work_block = classified.get("work_experience")
        if work_block:
            return _parse_loose_experience_entries(work_block[2])
        return []

    entries: List[ExperienceEntry] = []
    for heading_line, _, body in role_blocks:
        raw_heading = heading_line[3:].strip()  # remove "## "
        entry = _parse_experience_entry(raw_heading, body)
        entries.append(entry)

    return entries


def _parse_loose_experience_entries(body: str) -> List[ExperienceEntry]:
    """Parse common PDF/plaintext resume experience blocks.

    This is a repair path for resumes that preserve a Professional Experience
    section but do not use Markdown role headings.
    """
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return []

    starts: List[int] = []
    for i, line in enumerate(lines):
        if line.startswith(("-", "*", "+")):
            continue
        if _contains_date_range(line) and starts and i - starts[-1] <= 2:
            continue
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        next_next = lines[i + 2] if i + 2 < len(lines) else ""
        if _looks_like_loose_experience_start(line, next_line, next_next):
            starts.append(i)

    if not starts:
        return []

    entries: List[ExperienceEntry] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        segment = lines[start:end]
        entry = _parse_loose_experience_segment(segment)
        if entry and (entry.company or entry.role):
            entries.append(entry)
    return entries


def _looks_like_loose_experience_start(line: str, next_line: str, next_next: str) -> bool:
    if _contains_date_range(line):
        return True
    if next_line and _contains_date_range(next_line):
        return True
    if next_next and _contains_date_range(next_next) and not line.endswith("."):
        return True
    if "|" in line and next_line and not next_line.startswith(("-", "*", "+")):
        return _contains_date_range(next_line) or "|" in next_line
    return False


def _contains_date_range(text: str) -> bool:
    month_range = re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec|"
        r"January|February|March|April|June|July|August|September|October|November|December)"
        r"\s+\d{4}\s*(?:-|–|—|to)\s*(?:Present|Current|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec|"
        r"January|February|March|April|June|July|August|September|October|November|December)\s+\d{4})",
        text,
        re.IGNORECASE,
    )
    year_range = re.search(
        r"\b\d{4}\s*(?:-|–|—|to)\s*(?:Present|Current|\d{4})\b",
        text,
        re.IGNORECASE,
    )
    return bool(month_range or year_range)


def _extract_date_range(text: str) -> tuple[str, str]:
    pattern = re.compile(
        r"\b((?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec|"
        r"January|February|March|April|June|July|August|September|October|November|December)"
        r"\s+\d{4}\s*(?:-|–|—|to)\s*(?:Present|Current|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec|"
        r"January|February|March|April|June|July|August|September|October|November|December)\s+\d{4}))|"
        r"(?:\d{4}\s*(?:-|–|—|to)\s*(?:Present|Current|\d{4})))",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return "", text
    dates = match.group(1).strip()
    rest = (text[:match.start()] + text[match.end():]).strip(" |,-")
    return dates, rest


def _parse_loose_experience_segment(segment: List[str]) -> Optional[ExperienceEntry]:
    date_idx = next((i for i, line in enumerate(segment) if _contains_date_range(line)), None)
    if date_idx is not None:
        header_lines = segment[:date_idx + 1]
        body_lines = segment[date_idx + 1:]
    else:
        header_lines = []
        body_lines = []
        in_body = False
        for line in segment:
            if line.startswith(("-", "*", "+")):
                in_body = True
            if in_body:
                body_lines.append(line)
            else:
                header_lines.append(line)

    if not header_lines:
        return None

    company = ""
    role = ""
    location = ""
    dates = ""

    first = header_lines[0]
    second = header_lines[1] if len(header_lines) > 1 else ""

    if "|" in first and second and "|" in second:
        left = [p.strip() for p in first.split("|") if p.strip()]
        right = [p.strip() for p in second.split("|") if p.strip()]
        company = left[0] if left else ""
        location = left[1] if len(left) > 1 else ""
        role = right[0] if right else ""
        dates = right[1] if len(right) > 1 else ""
    elif "|" in first and _contains_date_range(first):
        parts = [p.strip() for p in first.split("|") if p.strip()]
        if len(parts) >= 4:
            company, role, location, dates = parts[0], parts[1], parts[2], parts[3]
        elif len(parts) == 3:
            company, role, dates = parts
        elif len(parts) == 2:
            company, dates = parts
    else:
        # Two-line header: company/location then role/dates
        # "Grant Thornton Bharat, Chennai, India" / "Financial Transformation Consultant, Jul 2025 - Present"
        if len(header_lines) == 2 and _contains_date_range(second) and not _contains_date_range(first):
            company, first_role, location = _split_loose_company_role_location(first)
            role_date = second
            dates, role_from_date = _extract_date_range(role_date)
            # If second line is pure date (no role text), keep role from first line
            role = first_role if first_role and not role_from_date else (role_from_date or first_role)
            role = role.strip(", ")
        else:
            combined = " ".join(header_lines[:3])
            dates, without_dates = _extract_date_range(combined)
            if "|" in without_dates:
                parts = [p.strip() for p in without_dates.split("|") if p.strip()]
                company = parts[0] if parts else ""
                role = parts[1] if len(parts) > 1 else ""
                location = parts[2] if len(parts) > 2 else ""
            else:
                company, role, location = _split_loose_company_role_location(without_dates)

    description_lines: List[str] = []
    bullet_lines: List[str] = []
    in_bullets = False
    for line in body_lines:
        if line.startswith(("-", "*", "+")):
            in_bullets = True
            bullet_lines.append(line)
        elif in_bullets and bullet_lines:
            bullet_lines[-1] += " " + line
        else:
            description_lines.append(line)
    bullets = _process_bullets(bullet_lines)

    return ExperienceEntry(
        role=_sanitize_text(role, context="heading"),
        company=_sanitize_text(company),
        location=_sanitize_text(location),
        dates=_sanitize_text(dates, context="daterange"),
        description=" ".join(_sanitize_text(l) for l in description_lines).strip(),
        bullets=bullets,
    )


def _split_loose_company_role_location(text: str) -> tuple[str, str, str]:
    text = text.strip(" |,-")
    location_match = re.search(
        r"\b(Remote(?:\s*-\s*[A-Z][A-Za-z ]+(?:,\s*[A-Z][A-Za-z ]+)?)?|Chennai,\s*India|Bangalore,\s*India|"
        r"Mumbai,\s*India|Delhi,\s*India|Toronto,\s*Canada)\b",
        text,
    )
    location = ""
    if location_match:
        location = location_match.group(1).strip()
        text = (text[:location_match.start()] + text[location_match.end():]).strip(" |,-")

    # Handle "Role at Company" format (e.g. "Financial Transformation Consultant at Grant Thornton")
    # Split on " at " where "at" is surrounded by spaces — not part of a word.
    # Also strip trailing em-dash artefacts left after location/date removal.
    text = re.sub(r"\s*[–—]\s*$", "", text).strip(" |,-\t")
    at_match = re.search(r"\s+at\s+", text, re.IGNORECASE)
    if at_match:
        role_part = text[:at_match.start()].strip(" |,-")
        company_part = text[at_match.end():].strip(" |,-")
        if role_part and company_part:
            return company_part, role_part, location

    role_keywords = [
        "Category Manager", "Assistant Fashion Manager", "Founder",
        "Merchandiser", "Buyer", "Manager", "Analyst", "Engineer",
        "Consultant", "Developer", "Director", "Associate", "Executive",
        "Specialist", "Coordinator", "Lead", "Head",
    ]
    for keyword in role_keywords:
        idx = text.lower().find(keyword.lower())
        if idx > 0:
            return text[:idx].strip(" |,-"), text[idx:].strip(" |,-"), location

    return text, "", location


def _parse_experience_entry(heading: str, body: str) -> ExperienceEntry:
    """Parse a single experience entry from heading and body."""
    role, company, location, dates = _parse_role_heading(heading)

    # Split body into description (non-bullet paragraphs) and bullets
    description_parts: List[str] = []
    bullet_lines: List[str] = []
    in_bullets = False

    if body:
        for line in body.strip().split("\n"):
            stripped = line.strip()
            if not stripped:
                if in_bullets:
                    # Empty line in bullet section: could be separator or end
                    continue
                else:
                    # Empty line before bullets starts the bullet section
                    continue
            if re.fullmatch(r"[-*_]{2,}", stripped):
                continue

            # Check if this is a bullet line
            if re.match(r"^\s*[-*+]\s", stripped):
                in_bullets = True
                bullet_lines.append(stripped)
            elif in_bullets:
                # Continuation of previous bullet (indented or paragraph after bullet)
                # Append to last bullet or treat as new bullet content
                if re.fullmatch(r"[-*_]{2,}", stripped):
                    continue
                if bullet_lines:
                    bullet_lines[-1] += " " + stripped
                else:
                    bullet_lines.append(stripped)
            else:
                # Non-bullet paragraph before bullets = description
                metadata = _strip_markdown_formatting(stripped)
                if _contains_date_range(metadata):
                    meta_dates, meta_location = _split_dates_location_metadata(metadata)
                    if meta_dates:
                        dates = meta_dates
                    if meta_location and not location:
                        location = meta_location
                else:
                    description_parts.append(_sanitize_text(stripped))

    # Process bullets (deduplicate, split collapsed, clean)
    bullets = _process_bullets(bullet_lines)

    return ExperienceEntry(
        role=_sanitize_text(role, context='heading'),
        company=_sanitize_text(company),
        location=_sanitize_text(location),
        dates=_sanitize_text(dates, context='daterange'),
        description="\n".join(description_parts).strip(),
        bullets=bullets,
    )


def _parse_role_heading(heading: str) -> Tuple[str, str, str, str]:
    """Parse a role heading into (role, company, location, dates).

    Input formats:
        "AI Engineer — Omnex Systems, Chennai (Jul 2025 – Present)"
        "Data Analyst - Positive Integers Pvt Ltd, Chennai (Sep 2019 – May 2020)"
        "Co-Founder / AI Engineer — Emote (emotenow.app) (Apr 2024 – Present)"
    """
    role = heading
    company = ""
    location = ""
    dates = ""

    # Extract dates from parentheses at end
    m = DATES_RE.search(heading)
    if m and _contains_date_range(m.group(1)):
        dates = m.group(1).strip()
        heading = heading[:m.start()].strip()

    # Split on em dash or spaced hyphen
    m = ROLE_HEADING_RE.search(heading)
    if m:
        role = m.group("role").strip()
        rest = m.group("rest").strip()

        # Split rest into company and location
        # Company may contain URL in parentheses like "Emote (emotenow.app)"
        if "(" in rest and ")" in rest and "," not in rest[:rest.find("(")]:
            # "Emote (emotenow.app)" or similar
            company = rest.strip()
            location = ""
        elif "," in rest:
            parts = rest.split(",", 1)
            company = parts[0].strip()
            location = parts[1].strip() if len(parts) > 1 else ""
        else:
            company = rest.strip()
            location = ""

    return role, company, location, dates


def _split_dates_location_metadata(text: str) -> Tuple[str, str]:
    """Split a leading metadata line like '2025 - Present | Chennai, India'."""
    text = _sanitize_text(text, context="daterange").strip()
    parts = [p.strip() for p in re.split(r"\s*\|\s*", text) if p.strip()]
    dates = ""
    location = ""
    for part in parts:
        if not dates and _contains_date_range(part):
            dates = part
        elif not location:
            location = part
    return dates, location


def _process_bullets(bullet_lines: List[str]) -> List[str]:
    """Process bullet lines: strip markers, detect collapsed bullets, clean up."""
    bullets: List[str] = []

    for line in bullet_lines:
        # Strip bullet marker
        cleaned = re.sub(r"^\s*[-*+]\s*", "", line).strip()
        if not cleaned:
            continue

        # Detect collapsed bullets: "text1. - text2. - text3"
        split_bullets = _split_collapsed_bullets(cleaned)
        bullets.extend(split_bullets)

    # Clean up: fix common artifacts
    cleaned_bullets: List[str] = []
    for b in bullets:
        b = b.strip()
        if not b:
            continue
        # Fix "and. X" → "and X" (period before space typo from Council)
        b = re.sub(r"\band\.\s+([A-Z])", r"and \1", b)
        # Sanitize em dashes and arrows (BUG 2 + BUG 3 fix)
        b = _sanitize_text(b)
        cleaned_bullets.append(b)

    return cleaned_bullets


def _split_collapsed_bullets(text: str) -> List[str]:
    """Split a single line that contains multiple collapsed bullets.

    Detects patterns like:
      "Built system X. - Designed system Y. - Drove performance Z."
      "Analyzed financial data for NBFC. - Developed dashboards using Tableau."

    Returns a list of individual bullet strings.
    """
    # Strategy 1: split on ". - " or ". — " followed by capital letter
    # This indicates sentence boundary + bullet separator
    if COLLAPSED_BULLET_RE.search(text):
        parts = COLLAPSED_BULLET_RE.split(text)
        if len(parts) >= 2:
            if all(len(p.strip()) > 15 for p in parts if p.strip()):
                return [p.strip() for p in parts if p.strip()]

    # Strategy 2: fallback to wider pattern (space-dash-space + capital)
    # Only use this if we find multiple such patterns on one long line
    if len(text) > 100:
        boundaries = list(COLLAPSED_BULLET_FALLBACK_RE.finditer(text))
        if len(boundaries) >= 2:
            parts = COLLAPSED_BULLET_FALLBACK_RE.split(text)
            if all(len(p.strip()) > 15 for p in parts if p.strip()):
                return [p.strip() for p in parts if p.strip()]

    # No collapsed bullets detected
    return [text]


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers: Achievements
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_achievements(classified: dict) -> List[str]:
    """Parse achievements section into list of achievement strings."""
    achievements_block = classified.get("achievements")
    if not achievements_block:
        return []

    _, _, body = achievements_block
    if not body:
        return []

    achievements: List[str] = []
    for line in body.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"[-*_]{2,}", stripped):
            continue
        # Strip bullet marker
        cleaned = re.sub(r"^\s*[-*+]\s*", "", stripped)
        if re.fullmatch(r"[-*_]{2,}", cleaned.strip()):
            continue
        if cleaned:
            achievements.append(_sanitize_text(cleaned))

    return achievements


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers: Education
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_education(classified: dict) -> List[EducationEntry]:
    """Parse education bullet list into EducationEntry list.

    Format:
        - **Degree** — Institution, Location (Dates)
        - Degree — Institution (Dates)
        - **M.Sc. Statistics and Machine Learning** — Linköping University, Sweden (2020–2022)
    """
    education_block = classified.get("education")
    if not education_block:
        return []

    _, _, body = education_block
    if not body:
        return []

    entries: List[EducationEntry] = []
    pending_institution: str = ""
    
    for line in body.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"[-*_]{2,}", stripped):
            continue

        # Strip bullet marker
        is_bullet = bool(re.match(r"^\s*[-*+]\s+", stripped))
        cleaned = re.sub(r"^\s*[-*+]\s*", "", stripped)
        if not cleaned:
            continue
        if re.fullmatch(r"[-*_]{2,}", cleaned.strip()):
            continue

        if is_bullet and entries and not re.search(r"\s+[—\-–]\s+", cleaned):
            existing = entries[-1].details.strip()
            addition = _sanitize_text(_strip_markdown_formatting(cleaned))
            entries[-1].details = f"{existing} {addition}".strip() if existing else addition
            continue

        degree, institution, dates, details = _parse_education_line(cleaned)
        
        # Multi-line format: institution line followed by degree+dates line
        # "Stoa School, Remote, India" then "General MBA Program, Sept 2023 - Apr 2024"
        has_dates = bool(dates) or bool(re.search(r"\b\d{4}\b", cleaned))
        looks_like_institution = not has_dates and not re.search(r"\s+[—\-–]\s+", cleaned) and not is_bullet
        
        if looks_like_institution and not pending_institution:
            pending_institution = cleaned
            continue
        
        if pending_institution:
            # Pair: institution line + degree/dates line
            institution = _strip_markdown_formatting(pending_institution)
            pending_institution = ""
            # Parse degree and dates from this line
            # Format: "General MBA Program, Sept 2023 - Apr 2024"
            # or "B.E. Electronics and Communications Engineering, Jul 2016 - Sept 2020"
            degree = _strip_markdown_formatting(cleaned)
            dates = ""
            details = ""
            # Extract date range
            dm = re.search(r",?\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)\s+\d{4}\s*(?:-|–|—|to)\s*(?:Present|Current|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)\s+\d{4}))", degree)
            if dm:
                dates = dm.group(1).strip()
                degree = degree[:dm.start()].strip().rstrip(',')
        
        entries.append(EducationEntry(
            degree=degree,
            institution=institution,
            dates=dates,
            details=details,
        ))

    return entries


def _parse_education_line(text: str) -> Tuple[str, str, str, str]:
    """Parse one education line into (degree, institution, dates, details).

    Pattern: **Degree** — Institution, Location (Dates)
    """
    degree = text
    institution = ""
    dates = ""
    details = ""

    # Extract dates from parentheses
    m_dates = re.search(r"\(([^)]+)\)\s*$", text)
    if m_dates:
        dates = m_dates.group(1).strip()
        text = text[:m_dates.start()].strip()

    # Split on em dash or spaced hyphen
    m_sep = re.search(r"\s+[—\-–]\s+", text)
    if m_sep:
        degree = _strip_markdown_formatting(text[:m_sep.start()].strip())
        rest = text[m_sep.end():].strip()

        # Rest may be "Institution, Location" or just "Institution"
        if "," in rest:
            parts = rest.split(",", 1)
            institution = _strip_markdown_formatting(parts[0].strip())
            details = _strip_markdown_formatting(parts[1].strip()) if len(parts) > 1 else ""
        else:
            institution = _strip_markdown_formatting(rest)
    else:
        degree = _strip_markdown_formatting(text)

    if details and not dates and _contains_date_range(details):
        dates, details = _extract_date_range(details)
        details = details.strip(" ·,|-")

    return (
        _sanitize_text(degree),
        _sanitize_text(institution),
        _sanitize_text(dates, context='daterange'),
        _sanitize_text(details),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers: Projects
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_projects(classified: dict) -> List[str]:
    """Parse projects section into list of project strings."""
    projects_block = classified.get("projects")
    if not projects_block:
        return []

    _, _, body = projects_block
    if not body:
        return []

    projects: List[str] = []
    for line in body.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Strip bullet marker
        cleaned = re.sub(r"^\s*[-*+]\s*", "", stripped)
        if cleaned:
            projects.append(_sanitize_text(cleaned))

    return projects


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers: Thesis
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_thesis(classified: dict) -> Optional[str]:
    """Parse thesis section into a single string."""
    thesis_block = classified.get("thesis")
    if not thesis_block:
        return None

    _, _, body = thesis_block
    if not body or not body.strip():
        return None

    return _sanitize_text(body.strip())


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers: Languages
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_languages(classified: dict) -> List[str]:
    """Parse languages bullet list into list of language strings."""
    languages_block = classified.get("languages")
    if not languages_block:
        return []

    _, _, body = languages_block
    if not body:
        return []

    langs: List[str] = []
    for line in body.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Strip bullet marker
        cleaned = re.sub(r"^\s*[-*+]\s*", "", stripped)
        # Strip markdown formatting
        cleaned = _strip_markdown_formatting(cleaned)
        if cleaned:
            langs.append(_sanitize_text(cleaned))

    return langs


# ═══════════════════════════════════════════════════════════════════════════════
# Sanitization (BUG 2 + BUG 3 fix: earliest stage em dash + arrow removal)
# ═══════════════════════════════════════════════════════════════════════════════

def _sanitize_text(text: str, context: str = 'body') -> str:
    """Remove arrows, em dashes, en dashes from text.

    This is the EARLIEST possible sanitization stage. Every downstream
    consumer (HTML, PDF, LaTeX) gets clean text with no raw Unicode
    arrows or em dashes.

    Args:
        text: The text to sanitize
        context: 'heading' (role titles), 'body' (general text), or 'daterange' (date spans)
    """
    if not text:
        return text

    # ── Arrow replacement (BUG 3) ──
    text = re.sub(r'\s*→\s*', ' to ', text)
    text = re.sub(r'\s*←\s*', ' from ', text)
    text = re.sub(r'\s*↔\s*', ' to/from ', text)
    text = re.sub(r'\s*⇒\s*', ' => ', text)
    text = re.sub(r'\s*➔\s*', ' to ', text)

    # ── Em dash replacement (BUG 2) ──
    if context == 'heading':
        # "AI Engineer — Omnex" → "AI Engineer, Omnex"
        text = re.sub(r'\s*—\s*', ', ', text)
    elif context == 'daterange':
        text = text.replace('—', ' - ')
    else:  # body
        # Date ranges first (before fallback comma replacement):
        # "2020 — 2022" or "2020 — Present"
        text = re.sub(r'(\d{4})\s*—\s*(\d{4})', r'\1 - \2', text)
        text = re.sub(r'(\d{4})\s*—\s*(Present|Current)', r'\1 - \2', text)
        # "Jul 2025 — Present" or "Nov 2022 — Nov 2024"
        text = re.sub(
            r'([A-Z][a-z]{2,8}\s+\d{4})\s*—\s*([A-Z][a-z]{2,8}\s+\d{4})',
            r'\1 - \2', text
        )
        text = re.sub(
            r'([A-Z][a-z]{2,8}\s+\d{4})\s*—\s*(Present|Current)',
            r'\1 - \2', text
        )
        # Remaining em dashes in body: use comma replacement
        text = re.sub(r'\s*—\s*', ', ', text)

    # ── En dash → hyphen ──
    text = text.replace('–', '-')

    return text


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _strip_markdown_formatting(text: str) -> str:
    """Strip common markdown formatting from text: **bold**, *italic*, `code`, links."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Links: [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Images
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # Stray/unpaired markers (regex split artifacts)
    text = text.replace("**", "").replace("*", "")
    return text.strip()
