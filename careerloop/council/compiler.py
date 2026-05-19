"""
Resume Compiler — deterministic markdown parsing, contract building, and safe assembly.

Parsing uses mistune (AST-based) — no regex section-splitting.
Assembly is pure Python — zero LLM calls.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

import mistune

from careerloop.council.models import (
    CanonicalResume,
    ResumeSection,
    VisibilityClass,
    PreservationContract,
    SectionRewrites,
    QualityReport,
    LinkAudit,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Mistune AST → Markdown Renderer (private helper)
# ═══════════════════════════════════════════════════════════════════════════════

class _MarkdownRenderer:
    """Renders mistune AST nodes back to markdown text. Handles all common
    block and inline node types found in resume documents."""

    @classmethod
    def render(cls, nodes: list) -> str:
        parts: List[str] = []
        for node in nodes:
            rendered = cls._render_node(node)
            if rendered is not None:
                parts.append(rendered)
        # Join blocks with double-newline, drop trailing whitespace-only blocks
        return "\n\n".join(p for p in parts if p.strip() or p == "").strip()

    @classmethod
    def _render_node(cls, node: dict) -> str:
        ntype = node.get("type", "")
        children = node.get("children", [])

        if ntype == "text":
            return node.get("raw", "")

        elif ntype == "link":
            text = cls._render_inline(children)
            url = node.get("attrs", {}).get("url", "")
            return f"[{text}]({url})"

        elif ntype == "image":
            alt = node.get("attrs", {}).get("alt", "")
            url = node.get("attrs", {}).get("url", "")
            return f"![{alt}]({url})"

        elif ntype == "paragraph":
            return cls._render_inline(children)

        elif ntype == "heading":
            level = node.get("attrs", {}).get("level", 2)
            prefix = "#" * level
            return prefix + " " + cls._render_inline(children)

        elif ntype == "blank_line":
            return ""

        elif ntype == "list":
            items: List[str] = []
            for child in children:
                if child.get("type") == "list_item":
                    items.append(cls._render_node(child))
            return "\n".join(items)

        elif ntype == "list_item":
            text = cls._render_inline(children)
            # Detect ordered vs unordered from attrs if available
            bullet = node.get("attrs", {}).get("bullet", "-")
            return f"{bullet} {text}"

        elif ntype == "block_code":
            info = node.get("attrs", {}).get("info", "")
            code = node.get("raw", "")
            return f"```{info}\n{code}\n```"

        elif ntype == "codespan":
            return f"`{node.get('raw', '')}`"

        elif ntype == "emphasis":
            return f"*{cls._render_inline(children)}*"

        elif ntype == "strong":
            return f"**{cls._render_inline(children)}**"

        elif ntype == "block_quote":
            return "> " + cls._render_inline(children)

        elif ntype == "thematic_break":
            return "---"

        elif ntype == "line_break":
            return "\n"

        elif ntype == "softbreak":
            return "\n"

        elif ntype == "html":
            return node.get("raw", "")

        elif ntype == "block_html":
            return node.get("raw", "")

        elif ntype == "table":
            rows: List[str] = []
            for child in children:
                rows.append(cls._render_node(child))
            return "\n".join(rows)

        elif ntype == "table_row":
            cells: List[str] = []
            for child in children:
                cells.append(cls._render_node(child))
            return "| " + " | ".join(cells) + " |"

        elif ntype == "table_cell":
            return cls._render_inline(children)

        elif ntype == "footnote_ref":
            label = node.get("attrs", {}).get("label", "")
            return f"[^{label}]"

        elif ntype == "footnote_def":
            return ""  # footnotes handled inline in mistune AST

        # Fallback: render children inline
        if children:
            return cls._render_inline(children)
        return ""

    @classmethod
    def _render_inline(cls, children: list) -> str:
        """Render inline elements — no blank-line separators between them."""
        parts: List[str] = []
        for child in children:
            rendered = cls._render_node(child)
            if rendered is not None:
                parts.append(rendered)
        return "".join(parts)

    # ── Link extraction ────────────────────────────────────────────────────

    @classmethod
    def extract_links(cls, nodes: list) -> List[str]:
        """Recursively extract all link URLs from AST nodes."""
        links: List[str] = []
        for node in nodes:
            if node.get("type") == "link":
                url = node.get("attrs", {}).get("url", "")
                if url:
                    links.append(url)
            if node.get("type") == "image":
                url = node.get("attrs", {}).get("url", "")
                if url:
                    links.append(url)
            if "children" in node:
                links.extend(cls.extract_links(node["children"]))
        return links


# ═══════════════════════════════════════════════════════════════════════════════
# ResumeCompiler
# ═══════════════════════════════════════════════════════════════════════════════

class ResumeCompiler:
    """
    Deterministic logic for parsing, contract building, and assembling resumes.

    Parse   : mistune AST (no regex)
    Contract: rule-based (no LLM)
    Assemble: pure Python merge (no LLM)
    Audit   : link preservation verification
    """

    # ── Parse ──────────────────────────────────────────────────────────────

    # Known ALL-CAPS CV section headers (longest first — prevents partial matches)
    _PLAINTEXT_HEADERS = [
        "PROFESSIONAL EXPERIENCE",
        "WORK EXPERIENCE",
        "CERTIFICATIONS",
        "ACHIEVEMENTS",
        "EXPERIENCE",
        "EDUCATION",
        "SUMMARY",
        "SKILLS",
        "PROJECTS",
        "AWARDS",
    ]

    # Common city/country names that appear in PDF-extracted CV location strings.
    # Used to detect run-on boundaries like "IndiaCategoryManager".
    _LOCATION_TOKENS = [
        "India", "Canada", "USA", "UK", "Remote", "Chennai", "Bangalore",
        "Mumbai", "Delhi", "Hyderabad", "Pune", "Kolkata", "Noida",
        "Toronto", "London", "Singapore", "Sweden", "Germany", "Australia",
        "France", "Dubai", "UAE", "Netherlands", "Ireland", "Poland",
    ]

    @staticmethod
    def _preprocess_plaintext_cv(text: str) -> str:
        """Normalise plain-text / PDF-extracted CVs before AST parsing.

        Two independent passes — both run regardless of heading presence:

        Pass A (heading injection) — only when no ## headings exist:
          Injects ## section markers for ALL-CAPS headers that are run together
          with surrounding text.

        Pass B (intra-section cleanup) — always runs:
          PDF extraction destroys intra-section line-breaks.  This pass:
          1. Converts bullet characters (•●▸) to markdown list items.
          2. Splits run-on date/location boundaries:
             - "Present" or "Currently" followed immediately by uppercase.
             - A bare 4-digit year followed immediately by uppercase.
             - Known location tokens (India, Canada …) followed immediately
               by an uppercase letter.
        """
        # ── Pass A: inject ## headings ────────────────────────────────────
        if not re.search(r'^#{1,6}\s+\S', text, re.MULTILINE):
            combined = '|'.join(
                re.escape(h) for h in ResumeCompiler._PLAINTEXT_HEADERS
            )
            text = re.sub(r'(' + combined + r')', r'\n\n## \1\n\n', text)

        # ── Pass B: intra-section cleanup ─────────────────────────────────

        # 1. Bullet character normalisation: •, ●, ▸, ▶, ◆ → markdown "- "
        #    Insert a newline before each bullet so it starts on its own line.
        text = re.sub(r'[\u2022\u25CF\u25B8\u25B6\u25C6\u25E6\u2219]',
                      r'\n- ', text)

        # 2. "Present" or "Currently" immediately followed by uppercase
        #    → paragraph break before the new content.
        #    Example: "Nov 2025 – PresentBuilt the ..." → "Present\n\nBuilt"
        #    Note: no trailing \b — word boundary doesn't fire between two \w chars.
        text = re.sub(r'\b(Present|Currently)([A-Z])', r'\1\n\n\2', text)

        # 3. A 4-digit year immediately followed by an uppercase letter (no
        #    space).  E.g. "Aug 2024Chennai" → "Aug 2024\n\nChennai"
        #    Negative lookahead: don't split inside year-ranges like "2020–2022".
        text = re.sub(r'(\b\d{4})(?![–\-\d])([A-Z])', r'\1\n\n\2', text)

        # 4. Known location tokens immediately followed by uppercase letter.
        #    E.g. "IndiaCategory" → "India\nCategory"
        #    Note: no trailing \b — "India" + "C" are both \w, so \b doesn't fire.
        for loc in ResumeCompiler._LOCATION_TOKENS:
            text = re.sub(
                r'\b(' + re.escape(loc) + r')([A-Z])',
                r'\1\n\2',
                text,
            )

        # ── Tidy up ───────────────────────────────────────────────────────
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def parse_markdown(text: str, person_id: str = "default") -> CanonicalResume:
        """
        System 1: Document Parser (AST-based).

        Uses mistune to parse markdown into an AST, then walks the AST to
        extract sections bounded by headings. This handles code blocks,
        nested structures, and inline formatting correctly — no regex
        section-splitting.
        """
        text = ResumeCompiler._preprocess_plaintext_cv(text)
        md = mistune.create_markdown(renderer="ast")
        ast = md(text)

        sections: List[ResumeSection] = []
        warnings: List[str] = []

        current_heading: Optional[dict] = None
        current_body: List[dict] = []
        pre_heading_body: List[dict] = []
        seen_first_heading = False

        for node in ast:
            if node.get("type") == "heading":
                if not seen_first_heading:
                    seen_first_heading = True
                    # Content before the first heading → intro section
                    if pre_heading_body:
                        intro_text = _MarkdownRenderer.render(pre_heading_body)
                        if intro_text.strip():
                            sections.append(ResumeSection(
                                section_id="intro",
                                section_title="Intro/Contact",
                                normalized_type="contact",
                                visibility_class=VisibilityClass.PUBLIC,
                                raw_text=intro_text,
                                original_order=len(sections),
                                links=_MarkdownRenderer.extract_links(pre_heading_body),
                            ))
                        pre_heading_body = []

                # Flush previous section
                if current_heading is not None:
                    section = ResumeCompiler._build_section_from_ast(
                        current_heading, current_body, len(sections)
                    )
                    sections.append(section)

                current_heading = node
                current_body = []
            else:
                if not seen_first_heading:
                    pre_heading_body.append(node)
                else:
                    current_body.append(node)

        # Flush final section
        if current_heading is not None:
            section = ResumeCompiler._build_section_from_ast(
                current_heading, current_body, len(sections)
            )
            sections.append(section)
        elif pre_heading_body and not seen_first_heading:
            # Entire document has no headings — treat as single intro section
            intro_text = _MarkdownRenderer.render(pre_heading_body)
            if intro_text.strip():
                sections.append(ResumeSection(
                    section_id="intro",
                    section_title="Intro/Contact",
                    normalized_type="contact",
                    visibility_class=VisibilityClass.PUBLIC,
                    raw_text=intro_text,
                    original_order=0,
                    links=_MarkdownRenderer.extract_links(pre_heading_body),
                ))

        return CanonicalResume(
            person_id=person_id,
            sections=sections,
            parse_warnings=warnings,
        )

    @staticmethod
    def _build_section_from_ast(heading_node: dict, body_nodes: list, order: int) -> ResumeSection:
        """Build a ResumeSection from a heading AST node and its body nodes."""
        # Extract heading title from heading's children (text nodes)
        title = _MarkdownRenderer._render_inline(heading_node.get("children", [])).strip()

        # Render body to markdown
        body_text = _MarkdownRenderer.render(body_nodes)

        # Extract links from heading + body combined
        all_nodes = [heading_node] + body_nodes
        links = _MarkdownRenderer.extract_links(all_nodes)

        section_id = re.sub(r"[^a-z0-9_]+", "_", title.lower()).strip("_")
        normalized_type, visibility = ResumeCompiler._classify_section(title, body_text)

        return ResumeSection(
            section_id=section_id,
            section_title=title,
            normalized_type=normalized_type,
            visibility_class=visibility,
            raw_text=body_text,
            original_order=order,
            links=links,
        )

    # ── Classify ───────────────────────────────────────────────────────────

    @staticmethod
    def _classify_section(title: str, content: str) -> Tuple[str, VisibilityClass]:
        title_lower = title.lower()

        private_keywords = [
            "deal-breaker", "deal breaker", "target role", "salary",
            "preference", "internal", "frustration", "constraint",
            "private", "strategy metadata", "search preference",
            "outreach preference",
        ]
        public_keywords = [
            "experience", "summary", "profile", "skill", "education",
            "project", "achievement", "contact", "about", "thesis",
            "research", "publication", "language", "certification",
            "internship", "work experience", "about me", "professional experience",
        ]

        if any(k in title_lower for k in private_keywords):
            return "private_metadata", VisibilityClass.PRIVATE

        for k in public_keywords:
            if k in title_lower:
                return k.replace(" ", "_"), VisibilityClass.PUBLIC

        return "unknown", VisibilityClass.UNKNOWN

    # ── Contract ───────────────────────────────────────────────────────────

    @staticmethod
    def build_contract(resume: CanonicalResume, profile: dict) -> PreservationContract:
        """
        System 2: Document Preservation + Structure Contract.

        Pure rule-based — no LLM. Determines which sections are required,
        excluded, and what the ordering rules are.
        """
        required: List[str] = []
        exclude: List[str] = []
        unknown: List[str] = []

        for section in resume.sections:
            if section.visibility_class == VisibilityClass.PUBLIC:
                # Essential sections that should never be dropped
                if section.normalized_type in {"contact", "education", "experience", "work_experience", "professional_experience"}:
                    required.append(section.section_id)
            elif section.visibility_class == VisibilityClass.PRIVATE:
                exclude.append(section.section_id)
            else:
                unknown.append(section.section_id)

        return PreservationContract(
            required_public_sections=required,
            sections_to_exclude=exclude,
            unknown_sections_to_preserve=unknown,
            ordering_rules=[s.section_id for s in resume.sections if s.section_id not in exclude],
            link_preservation_rules={"all": "MUST_SURVIVE"},
        )

    # ── Assemble ───────────────────────────────────────────────────────────

    @staticmethod
    def assemble(
        resume: CanonicalResume,
        rewrites: SectionRewrites,
        contract: PreservationContract,
    ) -> str:
        """
        System 8: Safe Assembler (Deterministic — no LLM).

        Rules:
        1. Sections in original order
        2. Rewritten text ONLY where contract allows AND a rewrite exists
        3. PRIVATE sections completely excluded
        4. Original links preserved (verified post-assembly by caller)
        """
        output_parts: List[str] = []

        sorted_sections = sorted(resume.sections, key=lambda s: s.original_order)

        for section in sorted_sections:
            if section.section_id in contract.sections_to_exclude:
                continue

            # Heading (skip for intro — it's a synthetic section)
            if section.section_id != "intro":
                if output_parts:
                    output_parts.append("")  # blank line before heading
                output_parts.append(f"## {section.section_title}")
            elif section.section_title and section.section_id == "intro":
                # Intro section with content but no heading
                pass

            # Content: use rewrite if non-empty, otherwise fall back to original
            if section.section_id in rewrites.rewrites:
                rw = rewrites.rewrites[section.section_id].rewritten_text
                if rw:
                    output_parts.append(rw)
                elif section.raw_text:
                    output_parts.append(section.raw_text)  # fallback
            elif section.raw_text:
                output_parts.append(section.raw_text)

        return "\n\n".join(output_parts).strip() + "\n"

    # ── Link Audit ─────────────────────────────────────────────────────────

    @staticmethod
    def extract_links_from_text(text: str) -> List[str]:
        """Extract all link/image URLs from a markdown string via mistune AST."""
        md = mistune.create_markdown(renderer="ast")
        ast = md(text)
        return _MarkdownRenderer.extract_links(ast)

    @staticmethod
    def _verify_links_preserved(
        original_resume: CanonicalResume,
        final_text: str,
        contract: PreservationContract,
    ) -> LinkAudit:
        """
        Cross-check: every link in the original (non-excluded) sections
        must appear in the final output. Returns a LinkAudit with warnings
        for any missing links.
        """
        per_section_original: Dict[str, int] = {}
        per_section_final: Dict[str, int] = {}
        all_original_links: List[str] = []
        missing: List[str] = []
        warn: List[str] = []

        # Collect original links from non-excluded sections
        for section in original_resume.sections:
            if section.section_id in contract.sections_to_exclude:
                continue
            per_section_original[section.section_id] = len(section.links)
            all_original_links.extend(section.links)

        # Collect final links by parsing the assembled text
        final_links = ResumeCompiler.extract_links_from_text(final_text)

        # Build per-section-final (approximate — we match links globally)
        # For deterministic sections that weren't rewritten, links per section
        # should match exactly. For rewritten sections, we check globally.
        total_original = len(all_original_links)
        total_final = len(final_links)

        # Determine which original links are missing from the final output
        final_set = set(final_links)
        for link in all_original_links:
            if link not in final_set:
                missing.append(link)

        if missing:
            warn.append(
                f"LINK PRESERVATION WARNING: {len(missing)}/{total_original} "
                f"original links missing from assembled resume: {missing}"
            )

        # Per-section final links (approximate by scanning each section's text)
        for section in original_resume.sections:
            if section.section_id in contract.sections_to_exclude:
                continue
            # For each section, check how many of its original links
            # appear in the final text
            present = sum(1 for link in section.links if link in final_set)
            per_section_final[section.section_id] = present

        if total_final < total_original:
            warn.append(
                f"Link count decreased: {total_original} → {total_final}. "
                f"Possible link loss during rewrite or assembly."
            )

        return LinkAudit(
            per_section_original=per_section_original,
            per_section_final=per_section_final,
            total_original=total_original,
            total_final=total_final,
            missing_links=missing,
            warnings=warn,
        )

    # ── Quality Report ─────────────────────────────────────────────────────

    @staticmethod
    def generate_quality_report(
        resume: CanonicalResume,
        rewrites: SectionRewrites,
        contract: PreservationContract,
        claims_not_allowed: Optional[List[str]] = None,
    ) -> QualityReport:
        changed: List[str] = []
        unchanged: List[str] = []
        risks: List[str] = []
        needs_user_review: List[str] = []

        if claims_not_allowed is None:
            claims_not_allowed = []

        for section in resume.sections:
            if section.section_id in contract.sections_to_exclude:
                continue
            if section.section_id in rewrites.rewrites:
                rewrite_obj = rewrites.rewrites[section.section_id]
                changed.append(
                    f"Section '{section.section_title}' was rewritten ({rewrite_obj.change_type})"
                )
                if rewrite_obj.change_type == "REWRITE":
                    needs_user_review.append(
                        f"Section '{section.section_title}' was completely rewritten."
                    )
                if getattr(rewrite_obj, "risk_level", "") == "high":
                    risks.append(f"High risk rewrite in '{section.section_title}'")
            else:
                unchanged.append(section.section_title)

        for claim in claims_not_allowed:
            needs_user_review.append(f"Verify claim was not made: '{claim}'")

        confidence = round(
            len(rewrites.rewrites) / max(len(resume.sections), 1), 2
        )

        return QualityReport(
            what_changed=changed,
            what_did_not_change=unchanged,
            needs_user_review=needs_user_review,
            risks=risks,
            confidence=confidence,
        )
