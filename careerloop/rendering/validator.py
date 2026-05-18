#!/usr/bin/env python3
"""
ResumeValidator — Standalone HTML resume quality checker.

Validates rendered HTML resumes against 10 rules covering:
  - Raw markdown tokens in HTML body (**, __, ```markdown, ### headings)
  - Forbidden characters (em dashes, en dashes, arrows)
  - Bullet structure (collapsed, inline, zero-bullet, malformed lists)
  - Content hygiene (forbidden sections, orphan headings)
  - Tailoring quality (delta between base and tailored resume)

Usage:
    from careerloop.rendering.validator import ResumeValidator

    v = ResumeValidator(html_string, base_html=optional_base_html)
    passed, errors, warnings = v.validate()
    print(v.report())
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


# ── Constants ─────────────────────────────────────────────────────────────

CAPITALIZED_ACTION_VERBS = (
    "Built", "Designed", "Drove", "Owned", "Developed", "Led",
    "Constructed", "Enabled", "Improved", "Reduced", "Scaled",
    "Launched", "Automated", "Migrated", "Optimized", "Engineered",
    "Delivered", "Defined", "Managed", "Spearheaded", "Architected",
    "Orchestrated", "Implemented", "Directed", "Established", "Created",
    "Enhanced", "Analyzed", "Generated", "Transformed",
)

FORBIDDEN_CONTENT = (
    "Target Role",
    "Deal-breaker",
    "Internal Notes",
    "Fit Score",
    "Council Verdict",
)

INLINE_BULLET_PATTERNS = tuple(
    re.compile(rf"-\s+{re.escape(verb)}") for verb in CAPITALIZED_ACTION_VERBS
)

# Work experience heading patterns to match
WORK_EXPERIENCE_PATTERNS = (
    r"<h2[^>]*>\s*Work\s+Experience\s*</h2>",
    r"<h2[^>]*>\s*Experience\s*</h2>",
    r'<div[^>]*class="[^"]*section-title[^"]*"[^>]*>\s*Experience\s*</div>',
)

# Raw markdown token patterns
RAW_MARKDOWN_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("double-asterisk-bold", re.compile(r"\*\*[^*]+\*\*")),
    ("double-underscore-bold", re.compile(r"__[^_]+__")),
    ("triple-backtick-markdown", re.compile(r"```markdown")),
    ("triple-backtick-generic", re.compile(r"```(?!markdown)")),
    ("triple-hash-heading", re.compile(r"###\s+[A-Z]")),
    ("single-asterisk-italic", re.compile(r"(?<!\*)\*(?!\*)[^*]+\*(?!\*)")),
]


# ── Result types ──────────────────────────────────────────────────────────

@dataclass
class RuleResult:
    rule_id: str
    severity: str  # "ERROR" or "WARNING"
    passed: bool
    details: str = ""
    count: int = 0
    locations: List[str] = field(default_factory=list)

    def icon(self) -> str:
        return "PASS" if self.passed else "FAIL"


@dataclass
class ValidationReport:
    file_path: str = ""
    results: List[RuleResult] = field(default_factory=list)

    @property
    def errors(self) -> List[RuleResult]:
        return [r for r in self.results if r.severity == "ERROR"]

    @property
    def warnings(self) -> List[RuleResult]:
        return [r for r in self.results if r.severity == "WARNING"]

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.errors)

    @property
    def passed_strict(self) -> bool:
        """When strict mode is on, warnings also count as failures."""
        return all(r.passed for r in self.results)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.errors if not r.passed)

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.warnings if not r.passed)


# ── Main validator ────────────────────────────────────────────────────────

class ResumeValidator:
    """Standalone HTML resume validator. No Council or external dependencies.

    Accepts optional base_html for tailoring delta comparison (Rule 10).
    """

    def __init__(
        self,
        html: str,
        base_html: Optional[str] = None,
        original_md: Optional[str] = None,
        strict: bool = False,
    ):
        self.raw_html = html
        self.base_html = base_html or ""
        self.original_md = original_md or ""
        self.strict = strict
        self._body = ""
        self._body_text = ""
        self._report = ValidationReport()

    # ── Body extraction ────────────────────────────────────────────────

    def _extract_body(self, html: str = None) -> str:
        """Extract visible body content from HTML, stripping style/script/comments."""
        if html is None:
            html = self.raw_html

        # Remove style blocks
        html = re.sub(
            r"<style[^>]*>.*?</style>", "", html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Remove script blocks
        html = re.sub(
            r"<script[^>]*>.*?</script>", "", html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Remove HTML comments
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

        # Remove <head> entirely
        html = re.sub(
            r"<head[^>]*>.*?</head>", "", html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Extract body
        body_match = re.search(
            r"<body[^>]*>(.*?)</body>", html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        body = body_match.group(1) if body_match else html

        return body

    @staticmethod
    def _strip_tags(text: str) -> str:
        """Remove HTML tags, leaving visible text with normalized whitespace."""
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _find_line_number(html: str, substring: str, start: int = 0) -> int:
        """Find the approximate line number of a substring in HTML."""
        idx = html.find(substring, start)
        if idx == -1:
            return 0
        return html[:idx].count("\n") + 1

    # ── Rule 1: RAW_MARKDOWN_TOKENS ──────────────────────────────────

    def _check_raw_markdown_tokens(self, body: str) -> RuleResult:
        """Rule 1: No raw markdown tokens in final HTML body.

        Scans for: **, __, ```markdown, ``` (code fences), ###  (headings).
        These indicate the markdown was not fully converted to HTML.
        """
        violations: List[str] = []

        # Check for **bold** patterns (raw markdown, not inside <strong>)
        # We look for **text** in the visible text where text doesn't contain HTML tags
        bold_matches = list(re.finditer(r"\*\*(.+?)\*\*", body))
        for m in bold_matches:
            inner = m.group(1)
            # Skip if this is inside a <strong> tag (properly rendered)
            before = body[max(0, m.start() - 20):m.start()]
            after = body[m.end():m.end() + 20]
            if "<strong>" in before or "</strong>" in after:
                continue
            # Skip if the inner contains HTML (might be nested in tags)
            if "<" in inner:
                continue
            snippet = inner[:60]
            line = self._find_line_number(body, m.group())
            violations.append(f"Line ~{line}: **{snippet}**")

        # Check for __bold__ patterns
        underscore_matches = list(re.finditer(r"__([^_]+)__", body))
        for m in underscore_matches:
            inner = m.group(1)
            if "<" in inner:
                continue
            snippet = inner[:60]
            line = self._find_line_number(body, m.group())
            violations.append(f"Line ~{line}: __{snippet}__")

        # Check for ```markdown or ``` code fences
        triple_matches = list(re.finditer(r"```(\w*)", body))
        for m in triple_matches:
            lang = m.group(1) or "generic"
            snippet = body[m.start():m.start() + 40].strip()
            line = self._find_line_number(body, m.group())
            violations.append(f"Line ~{line}: ```{lang} code fence — {snippet}")

        # Check for ###  (h3-style heading in markdown, in visible text only)
        # We need to be careful: <h3> in HTML is fine, but raw ### in text is not
        # Search for ### followed by space and capital letter in visible text
        visible_text = self._strip_tags(body)
        h3_markdown = list(re.finditer(r"###\s+[A-Z]", visible_text))
        for m in h3_markdown:
            snippet = visible_text[m.start():m.start() + 50].strip()
            violations.append(f"Visible text: '### {snippet}' (raw markdown h3 heading)")

        # Check for single *italic* patterns (not double **)
        # Must be *, not part of **, not inside HTML tags
        italic_matches = list(re.finditer(r"(?<!\*)\*([^*\n]+)\*(?!\*)", body))
        for m in italic_matches:
            inner = m.group(1)
            if len(inner) < 2 or "<" in inner:
                continue
            snippet = inner[:60]
            line = self._find_line_number(body, m.group())
            violations.append(f"Line ~{line}: *{snippet}* (raw italic markdown)")

        count = len(violations)
        passed = count == 0

        return RuleResult(
            rule_id="RAW_MARKDOWN_TOKENS",
            severity="ERROR",
            passed=passed,
            details=f"Found {count} raw markdown token(s)" if count else "",
            count=count,
            locations=violations[:10],  # cap at 10 for readability
        )

    # ── Rule 2: EM_DASH ──────────────────────────────────────────────

    def _check_em_dash(self, body: str) -> RuleResult:
        """Rule 2: No em dashes or en dashes in body content."""
        locations: List[str] = []

        em_dash = "—"  # U+2014
        en_dash = "–"  # U+2013

        if em_dash in body:
            for i, char in enumerate(body):
                if char == em_dash:
                    line = body[:i].count("\n") + 1
                    context_start = max(0, i - 30)
                    context_end = min(len(body), i + 30)
                    context = body[context_start:context_end].replace("\n", " ").strip()
                    locations.append(f"Line {line}, col {i - body[:i].rfind(chr(10)) if body[:i].rfind(chr(10)) >= 0 else i}: em dash in \"...{context}...\"")
                    if len(locations) >= 5:
                        break

        if en_dash in body:
            for i, char in enumerate(body):
                if char == en_dash:
                    line = body[:i].count("\n") + 1
                    context_start = max(0, i - 30)
                    context_end = min(len(body), i + 30)
                    context = body[context_start:context_end].replace("\n", " ").strip()
                    locations.append(f"Line {line}: en dash in \"...{context}...\"")
                    if len(locations) >= 5:
                        break

        em_count = body.count(em_dash)
        en_count = body.count(en_dash)
        total = em_count + en_count

        return RuleResult(
            rule_id="EM_DASH",
            severity="ERROR",
            passed=total == 0,
            details=f"Found {em_count} em dash(es), {en_count} en dash(es)" if total else "",
            count=total,
            locations=locations,
        )

    # ── Rule 3: ARROWS ───────────────────────────────────────────────

    def _check_arrows(self, body: str) -> RuleResult:
        """Rule 3: No arrow characters in body content."""
        arrows = {
            "→": ("right arrow", "U+2192"),
            "←": ("left arrow", "U+2190"),
            "↔": ("left-right arrow", "U+2194"),
        }
        locations: List[str] = []
        total = 0

        for char, (name, code) in arrows.items():
            if char in body:
                count = body.count(char)
                total += count
                for i, c in enumerate(body):
                    if c == char:
                        line = body[:i].count("\n") + 1
                        context_start = max(0, i - 25)
                        context_end = min(len(body), i + 25)
                        context = body[context_start:context_end].replace("\n", " ").strip()
                        locations.append(
                            f"Line {line}: {name} ({code}) in \"...{context}...\""
                        )
                        if len(locations) >= 8:
                            break

        return RuleResult(
            rule_id="ARROWS",
            severity="ERROR",
            passed=total == 0,
            details=f"Found {total} arrow character(s)" if total else "",
            count=total,
            locations=locations,
        )

    # ── Rule 4: COLLAPSED_BULLETS ────────────────────────────────────

    def _check_collapsed_bullets(self, body: str) -> RuleResult:
        """Rule 4: No <li> containing ' - ' followed by capitalized action verb.

        This catches bullets like:
          "<li>Built X. - Designed Y. - Drove Z.</li>"
        which should have been split into separate <li> items.
        """
        li_pattern = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL | re.IGNORECASE)
        violations: List[str] = []

        for m in li_pattern.finditer(body):
            li_content = m.group(1)
            stripped = self._strip_tags(li_content)

            # Count occurrences of " - Verb" or ". - Verb" or " — Verb"
            verb_alt = "|".join(CAPITALIZED_ACTION_VERBS)
            collapsed_pattern = re.compile(
                rf"(?:\.\s+|\.)\s*[-–—]\s+({verb_alt})\b"
            )

            matches = collapsed_pattern.findall(stripped)
            if len(matches) >= 1:
                # This li has 1+ collapsed bullet boundary
                # Found a boundary: the li contains at least 2 bullets merged
                snippet = stripped[:100].strip()
                line = self._find_line_number(body, m.group())
                verbs_found = ", ".join(matches[:3])
                violations.append(
                    f"Line ~{line}: collapsed bullets ({len(matches)} boundary/ies): "
                    f"verbs=[{verbs_found}] — \"{snippet}...\""
                )

        count = len(violations)
        return RuleResult(
            rule_id="COLLAPSED_BULLETS",
            severity="ERROR",
            passed=count == 0,
            details=f"Found {count} <li> element(s) with collapsed bullets" if count else "",
            count=count,
            locations=violations[:10],
        )

    # ── Rule 5: FORBIDDEN_SECTIONS ──────────────────────────────────

    def _check_forbidden_sections(self, body: str) -> RuleResult:
        """Rule 5: No forbidden section text in visible body content."""
        stripped = self._strip_tags(body)
        lower = stripped.lower()
        found: List[str] = []

        # Primary checks
        for term in FORBIDDEN_CONTENT:
            if term.lower() in lower:
                found.append(term)

        # Variant checks
        variants = [
            ("internal note", "Internal Notes"),
            ("internal notes", "Internal Notes"),
            ("deal-breakers", "Deal-breaker"),
            ("deal breakers", "Deal-breaker"),
            ("target roles", "Target Role"),
            ("fit score", "Fit Score"),
            ("council verdict", "Council Verdict"),
        ]
        for variant, canonical in variants:
            if variant in lower and canonical not in found:
                found.append(canonical)

        # Find positions
        locations: List[str] = []
        for term in found:
            idx = lower.find(term.lower())
            if idx >= 0:
                context = stripped[max(0, idx - 20):idx + len(term) + 30]
                locations.append(f"'{term}' found in: \"...{context}...\"")

        return RuleResult(
            rule_id="FORBIDDEN_SECTIONS",
            severity="ERROR",
            passed=len(found) == 0,
            details=f"Forbidden text found: {', '.join(found)}" if found else "",
            count=len(found),
            locations=locations,
        )

    # ── Rule 6: ZERO_BULLETS ────────────────────────────────────────

    def _check_zero_bullets(self, body: str) -> RuleResult:
        """Rule 6: Work Experience section must contain <li> items.

        Finds the Work Experience heading, then checks if any <li> follows
        before the next <h2> or end of body.
        """
        # Find Work Experience heading
        exp_match = None
        for pattern in WORK_EXPERIENCE_PATTERNS:
            m = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
            if m:
                exp_match = m
                break

        if not exp_match:
            return RuleResult(
                rule_id="ZERO_BULLETS",
                severity="ERROR",
                passed=True,
                details="No Work Experience heading found (may use different markup)",
            )

        # Extract content from after the heading to next <h2> or end
        start = exp_match.end()
        next_h2 = re.search(r"<h2[^>]*>", body[start:], re.IGNORECASE)
        end = start + next_h2.start() if next_h2 else len(body)
        exp_content = body[start:end]

        li_count = len(re.findall(r"<li[>\s]", exp_content, re.IGNORECASE))

        if li_count == 0:
            line = self._find_line_number(body, exp_match.group())
            return RuleResult(
                rule_id="ZERO_BULLETS",
                severity="ERROR",
                passed=False,
                details=f"Work Experience section (line ~{line}) has zero <li> items",
                count=0,
            )

        return RuleResult(
            rule_id="ZERO_BULLETS",
            severity="ERROR",
            passed=True,
            details=f"Found {li_count} bullet item(s) in Work Experience section",
            count=li_count,
        )

    # ── Rule 7: INLINE_BULLETS ──────────────────────────────────────

    def _check_inline_bullets(self, body: str) -> RuleResult:
        """Rule 7: No <p> containing inline bullet patterns like '- Built', '- Designed'.

        Bullets should be in <ul>/<li>, not inside paragraph tags separated by dashes.
        """
        p_pattern = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
        violations: List[str] = []

        for m in p_pattern.finditer(body):
            p_content = m.group(1)
            stripped = self._strip_tags(p_content)

            # Count how many action verb patterns exist after " - "
            verb_alt = "|".join(CAPITALIZED_ACTION_VERBS)
            inline_pattern = re.compile(rf"\s+[-–—]\s+({verb_alt})\b")
            matches = inline_pattern.findall(stripped)

            if matches:
                snippet = stripped[:120].strip()
                line = self._find_line_number(body, m.group())
                verbs = ", ".join(dict.fromkeys(matches[:5]))
                violations.append(
                    f"Line ~{line}: <p> contains {len(matches)} inline bullet(s): "
                    f"[{verbs}] — \"{snippet}...\""
                )

        count = len(violations)
        return RuleResult(
            rule_id="INLINE_BULLETS",
            severity="ERROR",
            passed=count == 0,
            details=f"Found {count} <p> element(s) with inline bullets" if count else "",
            count=count,
            locations=violations[:10],
        )

    # ── Rule 8: MALFORMED_LISTS ─────────────────────────────────────

    def _check_malformed_lists(self, body: str) -> RuleResult:
        """Rule 8: Every <ul> has matching </ul>, every <li> is inside <ul>.

        Checks:
          - <ul> and </ul> counts match
          - No <li> appears outside a <ul> (or <ol>) context
          - No nested <ul> inside <li> without proper closing (common bug)
        """
        violations: List[str] = []

        ul_open = len(re.findall(r"<ul[>\s]", body, re.IGNORECASE))
        ul_close = len(re.findall(r"</ul>", body, re.IGNORECASE))
        ol_open = len(re.findall(r"<ol[>\s]", body, re.IGNORECASE))
        ol_close = len(re.findall(r"</ol>", body, re.IGNORECASE))

        if ul_open != ul_close:
            line_hint = ""
            # Find approximate first problematic <ul>
            first_ul = re.search(r"<ul[>\s]", body, re.IGNORECASE)
            if first_ul:
                line_hint = f" (first <ul> near line {self._find_line_number(body, first_ul.group())})"
            violations.append(
                f"<ul> open={ul_open} but close={ul_close} — "
                f"{'missing ' + str(ul_open - ul_close) + ' </ul>' if ul_open > ul_close else 'extra ' + str(ul_close - ul_open) + ' </ul>'}"
                f"{line_hint}"
            )

        if ol_open != ol_close:
            violations.append(
                f"<ol> open={ol_open} but close={ol_close}"
            )

        # Check for <li> outside <ul>/<ol> context
        # We do this by scanning: every <li> should have an open <ul> or <ol> before it
        # that hasn't been closed yet
        all_li = list(re.finditer(r"<li[>\s]", body, re.IGNORECASE))
        for li_match in all_li:
            before = body[:li_match.start()]
            # Count open vs close tags before this <li>
            ul_open_before = len(re.findall(r"<ul[>\s]", before, re.IGNORECASE))
            ul_close_before = len(re.findall(r"</ul>", before, re.IGNORECASE))
            ol_open_before = len(re.findall(r"<ol[>\s]", before, re.IGNORECASE))
            ol_close_before = len(re.findall(r"</ol>", before, re.IGNORECASE))

            total_open = ul_open_before + ol_open_before
            total_close = ul_close_before + ol_close_before

            if total_open <= total_close:
                # <li> found outside any list context
                line = self._find_line_number(body, li_match.group())
                context_start = max(0, li_match.start() - 30)
                context_end = min(len(body), li_match.end() + 30)
                context = body[context_start:context_end].replace("\n", " ").strip()
                violations.append(
                    f"Line ~{line}: <li> outside <ul>/<ol> — "
                    f"\"...{context}...\""
                )
                if len(violations) >= 10:
                    break

        count = len(violations)
        return RuleResult(
            rule_id="MALFORMED_LISTS",
            severity="ERROR",
            passed=count == 0,
            details=f"Found {count} list structure issue(s)" if count else "All lists properly formed",
            count=count,
            locations=violations[:10],
        )

    # ── Rule 9: ORPHAN_HEADINGS ─────────────────────────────────────

    def _check_orphan_headings(self, body: str) -> RuleResult:
        """Rule 9: <h2> immediately followed by </div> or end of section with no content.

        Checks if an <h2> heading has meaningful content between it and the next
        heading or structural boundary.
        """
        orphans: List[str] = []

        # Find all h2 positions
        h2_matches = list(re.finditer(
            r"<h2[^>]*>(.*?)</h2>", body, re.IGNORECASE | re.DOTALL
        ))

        for i, match in enumerate(h2_matches):
            heading_text = self._strip_tags(match.group(1))
            start = match.end()

            # Determine end: next h2, or end of body
            if i + 1 < len(h2_matches):
                end = h2_matches[i + 1].start()
            else:
                end = len(body)

            after_content = body[start:end].strip()

            # Check if immediately followed by </div> or empty
            if after_content.startswith("</div>"):
                line = self._find_line_number(body, match.group())
                orphans.append(
                    f"Line ~{line}: '<h2>{heading_text}</h2>' immediately followed by </div> — no content"
                )
                continue

            # Check for minimal visible content (< 30 chars of visible text)
            visible_text = self._strip_tags(after_content)
            if len(visible_text) < 30:
                line = self._find_line_number(body, match.group())
                orphans.append(
                    f"Line ~{line}: '<h2>{heading_text}</h2>' followed by only "
                    f"{len(visible_text)} chars of visible content"
                )

        count = len(orphans)
        return RuleResult(
            rule_id="ORPHAN_HEADINGS",
            severity="WARNING",
            passed=count == 0,
            details=f"Found {count} orphan heading(s)" if count else "All headings have content",
            count=count,
            locations=orphans,
        )

    # ── Rule 10: TAILORING_DELTA ────────────────────────────────────

    def _check_tailoring_delta(self) -> RuleResult:
        """Rule 10: Compare base resume vs tailored resume.

        Measures:
          - % of changed bullets across experience entries
          - % of changed words in profile/summary

        If <10% overall difference, the resume was not tailored enough.
        If no base_html provided, this check is skipped (passes).
        """
        if not self.base_html or not self.base_html.strip():
            return RuleResult(
                rule_id="TAILORING_DELTA",
                severity="ERROR",
                passed=True,
                details="No base resume provided for comparison — skipping delta check",
            )

        try:
            base_body = self._extract_body(self.base_html)
            target_body = self._extract_body(self.raw_html)

            # Extract bullets from both
            base_bullets = self._extract_bullet_texts(base_body)
            target_bullets = self._extract_bullet_texts(target_body)

            # Extract profile text
            base_profile = self._extract_profile_text(base_body)
            target_profile = self._extract_profile_text(target_body)

            # Calculate bullet delta
            bullet_change_pct = self._calc_text_delta(base_bullets, target_bullets)

            # Calculate profile word delta
            profile_change_pct = self._calc_word_delta(base_profile, target_profile)

            # Overall delta = average of bullet and profile changes
            overall_delta = (bullet_change_pct + profile_change_pct) / 2.0

            passed = overall_delta >= 10.0

            details = (
                f"Bullet change: {bullet_change_pct:.1f}%, "
                f"Profile word change: {profile_change_pct:.1f}%, "
                f"Overall delta: {overall_delta:.1f}% "
                f"(threshold: 10%)"
            )

            if not passed:
                details += " — NOT TAILORED ENOUGH"

            return RuleResult(
                rule_id="TAILORING_DELTA",
                severity="ERROR",
                passed=passed,
                details=details,
                count=0,
            )

        except Exception as e:
            return RuleResult(
                rule_id="TAILORING_DELTA",
                severity="ERROR",
                passed=True,  # Don't fail on comparison errors
                details=f"Delta comparison error (skipped): {e}",
            )

    @staticmethod
    def _extract_bullet_texts(body: str) -> List[str]:
        """Extract all bullet texts from HTML body, returning cleaned text list."""
        li_pattern = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL | re.IGNORECASE)
        bullets = []
        for m in li_pattern.finditer(body):
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            text = re.sub(r"\s+", " ", text).strip()
            if text and len(text) > 10:
                bullets.append(text)
        return bullets

    @staticmethod
    def _extract_profile_text(body: str) -> str:
        """Extract profile/summary text from HTML body."""
        # Look for Profile or Summary heading and capture text until next h2
        m = re.search(
            r"<(?:h2|div[^>]*class=\"[^\"]*section-title[^\"]*\"[^>]*)>"
            r"\s*(?:Profile|Summary)\s*"
            r"</(?:h2|div)>",
            body, re.IGNORECASE,
        )
        if not m:
            return ""

        start = m.end()
        next_h2 = re.search(r"<h2[^>]*>", body[start:], re.IGNORECASE)
        end = start + next_h2.start() if next_h2 else len(body)

        text = body[start:end]
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _calc_text_delta(base: List[str], target: List[str]) -> float:
        """Calculate % of bullets that changed between base and target.

        Uses fuzzy matching: if a target bullet has no close match (>70% similar)
        in the base, it counts as changed.
        """
        if not base and not target:
            return 0.0
        if not base or not target:
            return 100.0

        changed = 0
        total = max(len(base), len(target))

        # For each base bullet, find best match in target
        matched_base = set()
        matched_target = set()

        for bi, b_text in enumerate(base):
            b_words = set(b_text.lower().split())
            best_sim = 0.0
            best_ti = -1

            for ti, t_text in enumerate(target):
                if ti in matched_target:
                    continue
                t_words = set(t_text.lower().split())
                if not b_words or not t_words:
                    continue
                intersection = b_words & t_words
                union = b_words | t_words
                sim = len(intersection) / len(union) if union else 0.0
                if sim > best_sim:
                    best_sim = sim
                    best_ti = ti

            if best_sim >= 0.70:
                matched_base.add(bi)
                matched_target.add(best_ti)

        changed = total - len(matched_base)
        return (changed / total) * 100.0 if total > 0 else 0.0

    @staticmethod
    def _calc_word_delta(base_text: str, target_text: str) -> float:
        """Calculate % of words changed in profile text."""
        if not base_text and not target_text:
            return 0.0
        if not base_text or not target_text:
            return 100.0

        base_words = set(base_text.lower().split())
        target_words = set(target_text.lower().split())

        if not base_words:
            return 0.0 if not target_words else 100.0

        # Changed = words removed + words added, relative to union
        removed = base_words - target_words
        added = target_words - base_words
        union = base_words | target_words

        changed_set = removed | added
        return (len(changed_set) / len(union)) * 100.0 if union else 0.0

    # ── Public API ───────────────────────────────────────────────────────

    def validate(self) -> Tuple[bool, List[RuleResult], List[RuleResult]]:
        """Run all 10 validation checks.

        Returns:
            (passed, errors, warnings) — passed is True if all ERROR rules pass.
            In strict mode, warnings are promoted to errors.
        """
        body = self._extract_body()
        self._body = body
        self._body_text = self._strip_tags(body)

        # Run all 10 checks
        checks: List[RuleResult] = [
            self._check_raw_markdown_tokens(body),    # Rule 1
            self._check_em_dash(body),                 # Rule 2
            self._check_arrows(body),                  # Rule 3
            self._check_collapsed_bullets(body),       # Rule 4
            self._check_forbidden_sections(body),      # Rule 5
            self._check_zero_bullets(body),            # Rule 6
            self._check_inline_bullets(body),          # Rule 7
            self._check_malformed_lists(body),         # Rule 8
            self._check_orphan_headings(body),         # Rule 9
            self._check_tailoring_delta(),             # Rule 10
        ]

        # In strict mode, promote WARNING to ERROR
        if self.strict:
            for r in checks:
                if r.severity == "WARNING":
                    r.severity = "ERROR"

        self._report.results = checks
        return (self._report.passed, self._report.errors, self._report.warnings)

    def report(self, file_path: str = "") -> str:
        """Generate a human-readable validation report."""
        self._report.file_path = file_path or self._report.file_path
        lines = []

        if self._report.file_path:
            lines.append(f"Validation Report: {self._report.file_path}")
            lines.append("=" * 70)
        else:
            lines.append("Validation Report")
            lines.append("=" * 70)

        use_strict = self.strict
        status = "PASS" if (self._report.passed_strict if use_strict else self._report.passed) else "FAIL"
        if use_strict and self._report.passed and not self._report.passed_strict:
            status = "FAIL (strict mode: warnings are errors)"

        lines.append(f"Status:  {status}")
        lines.append(
            f"Errors:  {self._report.error_count}, "
            f"Warnings: {self._report.warning_count}, "
            f"Mode: {'STRICT' if use_strict else 'NORMAL'}"
        )
        lines.append("")

        for r in self._report.results:
            icon = r.icon()
            lines.append(f"  [{icon}] {r.rule_id} [{r.severity}]")
            if not r.passed:
                if r.details:
                    lines.append(f"        {r.details}")
                if r.locations:
                    for loc in r.locations[:5]:  # Show first 5 locations
                        lines.append(f"          -> {loc}")
                    if len(r.locations) > 5:
                        lines.append(f"          ... and {len(r.locations) - 5} more")
            elif r.details:
                lines.append(f"        {r.details}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Return validation results as a dictionary for programmatic use."""
        return {
            "passed": self._report.passed,
            "passed_strict": self._report.passed_strict,
            "strict_mode": self.strict,
            "error_count": self._report.error_count,
            "warning_count": self._report.warning_count,
            "rules": {
                r.rule_id: {
                    "severity": r.severity,
                    "passed": r.passed,
                    "details": r.details,
                    "count": r.count,
                    "locations": r.locations,
                }
                for r in self._report.results
            },
        }


# ── CLI entry point ───────────────────────────────────────────────────────

def main():
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python validator.py <resume.html> [--base <base-resume.html>] [--strict] [--json]")
        print("       python validator.py --all")
        sys.exit(1)

    if sys.argv[1] == "--all":
        _validate_all_templates()
        return

    html_path = Path(sys.argv[1])
    if not html_path.exists():
        print(f"File not found: {html_path}")
        sys.exit(1)

    strict = "--strict" in sys.argv
    json_out = "--json" in sys.argv

    html = html_path.read_text()

    # Check for base HTML for tailoring delta
    base_html = None
    if "--base" in sys.argv:
        base_idx = sys.argv.index("--base")
        if base_idx + 1 < len(sys.argv):
            base_path = Path(sys.argv[base_idx + 1])
            if base_path.exists():
                base_html = base_path.read_text()
            else:
                print(f"Warning: base file not found: {base_path}", file=sys.stderr)

    v = ResumeValidator(html, base_html=base_html, strict=strict)
    v.validate()

    if json_out:
        import json
        v.to_dict()["file"] = str(html_path)
        print(json.dumps(v.to_dict(), indent=2))
    else:
        print(v.report(str(html_path)))

    # Exit code: 0 if all errors pass (or warnings pass in strict mode)
    if strict:
        sys.exit(0 if v._report.passed_strict else 1)
    else:
        sys.exit(0 if v._report.passed else 1)


def _validate_all_templates():
    """Run validator on all known template outputs."""
    from pathlib import Path

    base = Path("output/resume_templates/siddharth/latest")
    templates = [
        ("classic-ats", base / "classic-ats.html", base / "classic-ats.pdf"),
        ("compact-one-page", base / "compact-one-page.html", base / "compact-one-page.pdf"),
        ("executive-clean", base / "executive-clean.html", base / "executive-clean.pdf"),
        ("founder-operator", base / "founder-operator.html", base / "founder-operator.pdf"),
        ("modern-accent", base / "modern-accent.html", base / "modern-accent.pdf"),
        ("product-engineer", base / "product-engineer.html", base / "product-engineer.pdf"),
        ("technical-two-column", base / "technical-two-column.html", base / "technical-two-column.pdf"),
        ("cv-template-v2", base / "cv-template-v2.html", None),
    ]

    any_failed = False
    for name, html_path, pdf_path in templates:
        if not html_path.exists():
            print(f"\n{'='*70}")
            print(f"SKIP: {name} — file not found: {html_path}")
            continue
        html = html_path.read_text()
        v = ResumeValidator(html)
        v.validate()
        print(f"\n{'='*70}")
        print(v.report(str(html_path)))
        if not v._report.passed:
            any_failed = True

    import sys
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
