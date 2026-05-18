#!/usr/bin/env python3
"""
fill-template.py v5 — Structured data-driven HTML resume converter.
Consumes NormalizedResume from the normalizer. No raw markdown parsing.

One data model, one normalizer, consumed by ALL renderers.
"""
import re, sys
from pathlib import Path
from html import escape

from careerloop.rendering.normalizer import normalize
from careerloop.rendering.resume_model import (
    NormalizedResume,
    HeaderInfo,
    SkillRow,
    ExperienceEntry,
    EducationEntry,
)

# ── Constants ───────────────────────────────────────────────────────────

ACTION_VERBS = {
    'Built', 'Designed', 'Drove', 'Owned', 'Developed', 'Led', 'Constructed',
    'Enabled', 'Improved', 'Enhanced', 'Analyzed', 'Created', 'Managed',
    'Reduced', 'Scaled', 'Shipped', 'Automated', 'Implemented', 'Delivered',
    'Launched', 'Optimized', 'Engineered', 'Architected', 'Directed',
    'Migrated', 'Integrated', 'Deployed', 'Configured', 'Established',
}

# ── Content cleaners (final safety net — normalizer handles most of this) ──

def sanitize(text: str) -> str:
    """Final-pass cleaning: collapse multiple spaces, trailing spaces before newlines."""
    text = re.sub(r'[^\S\n]{2,}', ' ', text)  # collapse multiple spaces (not newlines)
    text = re.sub(r' \n', '\n', text)  # trailing space before newline
    return text


def clean_ai_slop(text: str) -> str:
    """Reduce overused AI terms. Targets only the most overused patterns.

    Applied BEFORE normalization on raw markdown text.
    """
    # "agentic quality management" → "AI-driven quality management" (first occurrence only)
    text = re.sub(
        r'agentic quality management',
        'AI-driven quality management',
        text, count=1, flags=re.IGNORECASE
    )
    # "multi-agent orchestration" → "workflow orchestration" (after first use)
    first_match = re.search(r'multi-agent orchestration', text, re.IGNORECASE)
    if first_match:
        keep_until = first_match.end()
        before = text[:keep_until]
        after = text[keep_until:]
        after = re.sub(
            r'multi-agent orchestration',
            'workflow orchestration',
            after, flags=re.IGNORECASE
        )
        text = before + after
    return text


# ── Inline markdown → HTML ─────────────────────────────────────────────

def _inline(text: str) -> str:
    """Convert inline markdown to HTML. Preserves links, metrics, code."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


# ── Structured data → HTML formatters ──────────────────────────────────
# These consume NormalizedResume fields, NOT raw markdown.

def _profile_to_html(profile: str) -> str:
    """Convert profile text to HTML paragraph."""
    if not profile or not profile.strip():
        return ''
    return f'<div class="summary"><p>{_inline(sanitize(profile))}</p></div>'


def _skills_to_html(skills: list) -> str:
    """Convert List[SkillRow] to skills-grid HTML."""
    if not skills:
        return ''

    label_map = {
        'ai systems & agentic architectures': 'AI Systems',
        'ai systems and agentic architectures': 'AI Systems',
        'backend & real-time systems': 'Backend',
        'backend and real-time systems': 'Backend',
        'system design & orchestration': 'Systems Design',
        'system design and orchestration': 'Systems Design',
        'infra & observability': 'Infra',
        'infra and observability': 'Infra',
        'data & analytics': 'Data',
        'data and analytics': 'Data',
    }

    html = ['<div class="skills-grid">']
    for skill in skills:
        cat_lower = skill.label.lower()
        label = label_map.get(cat_lower, skill.label)
        tags = ' · '.join(_inline(tag) for tag in skill.items)
        html.append(f'<span class="cat">{_inline(label)}</span>')
        html.append(f'<span class="tags">{tags}</span>')
    html.append('</div>')
    return '\n'.join(html)


def _experience_to_html(experience: list) -> str:
    """Convert List[ExperienceEntry] to HTML."""
    if not experience:
        return '<p>See markdown output for experience details.</p>'

    parts = []
    for exp in experience:
        parts.append('<div class="exp-item">')
        parts.append('<div class="exp-header">')
        parts.append(f'<span class="role">{_inline(exp.role)}</span>')
        parts.append('<span class="exp-meta">')

        # Build company + location + dates
        meta = []
        if exp.company:
            loc_str = exp.company
            if exp.location:
                loc_str += f', {exp.location}'
            meta.append(f'<span class="company">{_inline(loc_str)}</span>')
        if exp.dates:
            meta.append(f'<span class="dates">{exp.dates}</span>')
        parts.append(''.join(meta))

        parts.append('</span>')
        parts.append('</div>')

        # Description (company context paragraph)
        if exp.description:
            parts.append(f'<p>{_inline(sanitize(exp.description))}</p>')

        # Bullets
        if exp.bullets:
            parts.append('<ul>')
            for bullet in exp.bullets:
                parts.append(f'<li>{_inline(sanitize(bullet))}</li>')
            parts.append('</ul>')

        parts.append('</div>')

    return '\n'.join(parts)


def _achievements_to_html(achievements: list) -> str:
    """Convert List[str] achievement strings to HTML with bold lead text."""
    if not achievements:
        return ''

    items = []
    for line in achievements:
        line = sanitize(line)
        if not line:
            continue
        # Bold the first segment: "**Title:** rest" or "Title: rest"
        if line.startswith('**') and '**' in line[2:]:
            pass  # already bolded
        elif ':' in line and len(line.split(':')[0]) < 80:
            parts = line.split(':', 1)
            line = f'<strong>{parts[0]}:</strong>{parts[1]}'
        items.append(f'<li>{_inline(line)}</li>')

    if not items:
        return ''
    return '<div class="achievements"><ul>\n' + '\n'.join(items) + '\n</ul></div>'


def _education_to_html(education: list, thesis: str = None) -> str:
    """Convert List[EducationEntry] to HTML bullet list."""
    if not education:
        return ''

    html = ['<ul>']
    for edu in education:
        line = f'<strong>{_inline(edu.degree)}</strong>'
        if edu.institution:
            line += f' - {_inline(edu.institution)}'
            if edu.details:
                line += f', {_inline(edu.details)}'
        if edu.dates:
            line += f' ({edu.dates})'
        html.append(f'<li>{line}</li>')
    html.append('</ul>')

    result = '\n'.join(html)

    if thesis:
        result += f'\n<h2>Master\'s Thesis</h2>\n<p class="thesis"><em>{_inline(sanitize(thesis))}</em></p>'

    return result


def _languages_to_html(languages: list) -> str:
    """Convert List[str] language strings to inline list HTML."""
    if not languages:
        return ''
    langs = ' · '.join(_inline(l) for l in languages)
    return f'<div class="lang-list"><span>{langs}</span></div>'


# ── HTML Generator ─────────────────────────────────────────────────────

def generate_html(resume: NormalizedResume, template_path: str) -> str:
    """Fill template with NormalizedResume data.

    Args:
        resume: Structured NormalizedResume from the normalizer.
        template_path: Path to the HTML template file.

    Returns:
        Filled HTML string ready for PDF generation.
    """
    assert isinstance(resume, NormalizedResume), \
        "generate_html must receive NormalizedResume, not raw markdown"

    template = Path(template_path).read_text()
    # Template has em dash in title ("{{NAME}} — CV") — replace carefully
    template = re.sub(r'\s*—\s*', ' - ', template)

    name = resume.header.name or 'Resume'

    # Build each section HTML from structured data
    profile_html = _profile_to_html(resume.profile)
    skills_html = _skills_to_html(resume.skills)
    exp_html = _experience_to_html(resume.experience)
    achievements_html = _achievements_to_html(resume.achievements)
    edu_html = _education_to_html(resume.education, resume.thesis)
    lang_html = _languages_to_html(resume.languages)

    # Replace placeholders
    html = template
    is_sidebar = '{{SIDEBAR_CONTACT}}' in html

    html = html.replace('{{NAME}}', name)
    if is_sidebar:
        html = html.replace('{{SECTION_SUMMARY}}',
            f'<div class="section"><div class="section-title">Profile</div><div class="profile-text">{_inline(sanitize(resume.profile))}</div></div>' if resume.profile else '')
        html = html.replace('{{SECTION_EXPERIENCE}}',
            f'<div class="section"><div class="section-title">Experience</div>{exp_html}</div>')
        html = html.replace('{{SECTION_ACHIEVEMENTS}}',
            f'<div class="section"><div class="section-title">Key Achievements</div><div class="achievements"><ul>{"".join(f"<li>{_inline(sanitize(a))}</li>" for a in resume.achievements)}</ul></div></div>' if resume.achievements else '')
    else:
        html = html.replace('{{SECTION_SUMMARY}}',
            f'<h2>Profile</h2>{profile_html}' if profile_html else '')
        html = html.replace('{{SECTION_SKILLS}}',
            f'<h2>Skills</h2>{skills_html}' if skills_html else '')
        html = html.replace('{{SECTION_EXPERIENCE}}',
            f'<h2>Work Experience</h2>{exp_html}')
        html = html.replace('{{SECTION_ACHIEVEMENTS}}',
            f'<h2>Key Achievements</h2>{achievements_html}' if achievements_html else '')
    html = html.replace('{{SECTION_EDUCATION}}',
        f'<h2>Education</h2>{edu_html}' if edu_html else '')
    html = html.replace('{{SECTION_LANGUAGES}}',
        f'<h2>Languages</h2>{lang_html}' if lang_html else '')

    # ── Sidebar template support ──────────────────────────────────────
    if '{{SIDEBAR_CONTACT}}' in html:
        # Role subtitle from profile first sentence
        role_subtitle = "AI Product Engineer"  # default
        if resume.profile:
            first_sentence = resume.profile.split('.')[0].strip()
            # Remove ** markers for the subtitle
            role_subtitle = re.sub(r'\*\*(.+?)\*\*', r'\1', first_sentence)[:120]

        html = html.replace('{{ROLE_SUBTITLE}}', role_subtitle)

        # Sidebar contact
        h = resume.header
        contact_lines = []
        if h.email: contact_lines.append(f'<div>{h.email}</div>')
        if h.phone: contact_lines.append(f'<div>{h.phone}</div>')
        if h.location: contact_lines.append(f'<div>{h.location}</div>')
        if h.portfolio_url:
            contact_lines.append(f'<div><a href="{h.portfolio_url}">{h.portfolio_display or "Portfolio"}</a></div>')
        if h.github_url:
            contact_lines.append(f'<div><a href="{h.github_url}">GitHub</a></div>')
        html = html.replace('{{SIDEBAR_CONTACT}}',
            f'<div class="sblock"><div class="stitle">Contact</div>{"".join(contact_lines)}</div>' if contact_lines else '')

        # Sidebar education (compact)
        if resume.education:
            edu_items = []
            for e in resume.education:
                item = f'<div class="edu-item"><div class="degree">{e.degree}</div>'
                if e.institution:
                    item += f'<div class="school">{e.institution}'
                    if e.dates: item += f', {e.dates}'
                    item += '</div>'
                item += '</div>'
                edu_items.append(item)
            html = html.replace('{{SIDEBAR_EDUCATION}}',
                f'<div class="sblock"><div class="stitle">Education</div>{"".join(edu_items)}</div>')
        else:
            html = html.replace('{{SIDEBAR_EDUCATION}}', '')

        # Sidebar skills (compact tag style)
        if resume.skills:
            skill_parts = []
            for sk in resume.skills:
                label = sk.label
                label_map = {
                    'AI Systems & Agentic Architectures': 'AI Systems',
                    'Backend & Real-Time Systems': 'Backend',
                    'System Design & Orchestration': 'Systems Design',
                    'Infra & Observability': 'Infra',
                    'Data & Analytics': 'Data',
                }
                label = label_map.get(label, label)
                # Take first 4-5 items max for compact display
                items = sk.items[:5]
                skill_parts.append(f'<div class="skill-cat">{label}</div>')
                skill_parts.append(f'<div class="skill-tags">{", ".join(items)}</div>')
            html = html.replace('{{SIDEBAR_SKILLS}}',
                f'<div class="sblock"><div class="stitle">Skills</div>{"".join(skill_parts)}</div>')
        else:
            html = html.replace('{{SIDEBAR_SKILLS}}', '')

        # Sidebar languages
        if resume.languages:
            html = html.replace('{{SIDEBAR_LANGUAGES}}',
                f'<div class="sblock"><div class="stitle">Languages</div><ul>{"".join(f"<li>{l}</li>" for l in resume.languages)}</ul></div>')
        else:
            html = html.replace('{{SIDEBAR_LANGUAGES}}', '')

        # Sidebar thesis
        if resume.thesis:
            html = html.replace('{{SIDEBAR_THESIS}}',
                f'<div class="sblock"><div class="stitle">Thesis</div><div style="font-size:8.5px;color:var(--slate)">{resume.thesis[:200]}...</div></div>')
        else:
            html = html.replace('{{SIDEBAR_THESIS}}', '')

    # Contact fields from HeaderInfo
    contact_replacements = {
        '{{PHONE}}': resume.header.phone,
        '{{EMAIL}}': resume.header.email,
        '{{LOCATION}}': resume.header.location,
        '{{PORTFOLIO_URL}}': resume.header.portfolio_url,
        '{{PORTFOLIO_DISPLAY}}': resume.header.portfolio_display,
        '{{GITHUB_URL}}': resume.header.github_url,
        '{{GITHUB_DISPLAY}}': resume.header.github_display,
        '{{LINKEDIN_URL}}': resume.header.linkedin_url,
        '{{LINKEDIN_DISPLAY}}': resume.header.linkedin_display,
    }
    for placeholder, value in contact_replacements.items():
        html = html.replace(placeholder, str(value))

    html = html.replace('{{PAGE_WIDTH}}', '8.5in')
    html = html.replace('{{PAGE_SIZE}}', 'letter')

    # Clean unused conditional blocks ({{#FIELD}}...{{/FIELD}})
    contact_field_map = {
        'PHONE': resume.header.phone,
        'PORTFOLIO_URL': resume.header.portfolio_url,
        'GITHUB_URL': resume.header.github_url,
        'LOCATION': resume.header.location,
        'LINKEDIN_URL': resume.header.linkedin_url,
    }
    for field, value in contact_field_map.items():
        has_val = bool(value)
        if not has_val:
            html = re.sub(
                r'\{\{#' + field + r'\}\}.*?\{\{/' + field + r'\}\}',
                '', html, flags=re.DOTALL
            )
        else:
            html = html.replace('{{#' + field + '}}', '')
            html = html.replace('{{/' + field + '}}', '')

    # Final validation: no em dashes in body
    body_start = html.find('<body>')
    body_end = html.find('</body>')
    if body_start >= 0 and body_end >= 0:
        body_html = html[body_start:body_end]
    else:
        body_html = html
    assert '—' not in body_html, "EM DASH FOUND IN BODY OUTPUT"
    assert '–' not in body_html, "EN DASH FOUND IN BODY OUTPUT"

    return html


# ── Main ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python fill-template.py <resume.md> <template.html> [output.html]")
        sys.exit(1)

    resume_path = sys.argv[1]
    template_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else resume_path.replace('.md', '.html')

    # ── Data contract assertion ──────────────────────────────────────
    md_text = Path(resume_path).read_text()

    # Pre-normalization: clean AI slop terms from raw markdown
    md_text = clean_ai_slop(md_text)

    resume = normalize(md_text)
    assert isinstance(resume, NormalizedResume), \
        "Renderer must consume NormalizedResume — normalizer returned wrong type"

    html = generate_html(resume, template_path)

    Path(output_path).write_text(html, encoding='utf-8')

    # ── Validation ────────────────────────────────────────────────────
    errors = []

    # Extract HTML body for content checks
    body_start = html.find('<body>')
    body_end = html.find('</body>')
    body_html = html[body_start:body_end] if body_start >= 0 and body_end >= 0 else html

    # Arrow characters in output
    arrow_chars = {'→': 'RIGHT ARROW', '←': 'LEFT ARROW', '↔': 'LEFT-RIGHT ARROW',
                   '⇒': 'RIGHT DOUBLE ARROW', '➔': 'HEAVY RIGHT ARROW'}
    for char, char_name in arrow_chars.items():
        if char in body_html:
            errors.append(f'{char_name} ({char}) found in output')

    # Em dash in body
    if '—' in body_html:
        errors.append('EM DASH found in body output')

    # Raw **bold** markers (BUG 1: markdown not converted to HTML)
    if '**' in body_html:
        errors.append('Raw **bold** markers found in HTML body — markdown not converted')

    # Collapsed bullet patterns in output
    collapsed_pattern = rf'\.\s+[-]\s+(?:{"|".join(sorted(ACTION_VERBS, key=len, reverse=True))})\b'
    collapsed_count = len(re.findall(collapsed_pattern, body_html))
    if collapsed_count > 0:
        errors.append(f'Collapsed bullet patterns remaining: {collapsed_count}')

    # AI slop terms in body
    slop_terms = ['agentic quality management']
    for term in slop_terms:
        if term in body_html.lower():
            errors.append(f'AI slop term still present: "{term}"')

    # QA summary
    print(f"✅ HTML: {output_path} ({len(html)} bytes)")
    print(f"   Name: {resume.header.name or '?'}")
    print(f"   Roles: {len(resume.experience)}")
    print(f"   Skills rows: {len(resume.skills)}")
    print(f"   Achievements: {len(resume.achievements)}")
    print(f"   Education entries: {len(resume.education)}")
    print(f"   Languages: {len(resume.languages)}")
    print(f"   Em dashes in body: {body_html.count(chr(0x2014))} (0 expected)")
    print(f"   Arrows: {sum(html.count(c) for c in arrow_chars)} (0 expected)")
    print(f"   Collapsed bullet patterns: {collapsed_count} (0 expected)")

    if errors:
        print(f"\n⚠️  VALIDATION FAILURES ({len(errors)}):")
        for e in errors:
            print(f"   ❌ {e}")
    else:
        print(f"\n   All validations passed ✅")
