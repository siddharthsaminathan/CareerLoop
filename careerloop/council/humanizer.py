"""
Humanizer — Anti-AI detection + human communication normalization.

5-phase pipeline:
  Phase 1 (DETERMINISTIC): AI slop detection — flag banned words/phrases
  Phase 2 (DETERMINISTIC): Recruiter realism check — structural red flags
  Phase 3 (LLM): Surgical humanize — rewrite flagged sentences minimally
  Phase 4 (LLM): Tone adaptation — match company/role context
  Phase 5 (DETERMINISTIC): Output sanitization — smart quotes, encoding, whitespace

Usage:
    h = Humanizer(llm_client)
    result = h.humanize(text, mode="resume", context={"company_type": "startup"})
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from careerloop.council.humanizer_rules import (
    BANNED_WORDS,
    BANNED_PHRASES,
    BANNED_WORD_REPLACEMENTS,
    TONE_PROFILES,
    MAX_CONSECUTIVE_I_STARTS,
    BULLET_ACTION_VERBS,
)
from careerloop.council.humanizer_prompts import (
    SLOP_DETECTOR_SYSTEM,
    RECRUITER_REALISM_SYSTEM,
    SURGICAL_HUMANIZE_SYSTEM,
    TONE_ADAPTER_SYSTEM,
)


@dataclass
class HumanizerFlag:
    text: str
    category: str  # buzzword, exaggeration, vagueness, cadence, filler, banned_word
    suggestion: str
    position: int  # character offset in original text


@dataclass
class HumanizerResult:
    original_text: str
    humanized_text: str
    flags: list = field(default_factory=list)
    changes_made: int = 0
    recruiter_concerns: list = field(default_factory=list)


class Humanizer:
    """4-phase humanization pipeline for AI-generated career communication."""

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: Optional LLM client with a complete_json(system, user) -> dict method.
                        If None, Phases 3-4 will use deterministic fallbacks.
        """
        self.llm = llm_client

    def humanize(self, text: str, mode: str = "resume",
                 context: Optional[dict] = None) -> HumanizerResult:
        """Main entry point. Run 4-phase pipeline.

        Args:
            text: Raw AI-generated text to humanize.
            mode: "resume" | "cover_note" | "recruiter_message" | "follow_up"
            context: {
                "company_type": "startup" | "growth" | "enterprise" | "default",
                "tone": str (from PositioningStrategy.tone_guidance),
            }

        Returns:
            HumanizerResult with original_text, humanized_text, flags, and concerns.
        """
        if not text or not text.strip():
            return HumanizerResult(
                original_text=text or "",
                humanized_text=text or "",
            )

        if context is None:
            context = {}

        # Phase 1: Detect AI slop (deterministic)
        flags = self._detect_slop(text)

        # Phase 2: Recruiter realism check (deterministic)
        concerns = self._check_realism(text, flags)

        # Phase 3: Surgical humanize (LLM if available, else deterministic)
        humanized = self._surgical_humanize(text, flags, mode)

        # Phase 4: Tone adaptation (LLM if available, else deterministic rules)
        adapted = self._adapt_tone(humanized, context, mode)

        # Phase 5: Sanitize output (deterministic — em dashes, arrows, encoding)
        sanitized = self._sanitize_output(adapted)
        if mode == "resume":
            safe, _issues = _markdown_structure_safe(text, sanitized)
            if not safe:
                sanitized = self._sanitize_output(text)

        return HumanizerResult(
            original_text=text,
            humanized_text=sanitized,
            flags=flags,
            changes_made=len(flags),
            recruiter_concerns=concerns,
        )

    # ─── Phase 1: AI Slop Detection (DETERMINISTIC) ──────────────────────────

    def _detect_slop(self, text: str) -> list:
        """Phase 1: Detect AI-generated language patterns (deterministic).

        Checks:
        1. Banned words (exact + lemma match, e.g. "leveraged" matches "leverage")
        2. Banned phrases (case-insensitive substring)
        3. Consecutive "I"-starting sentences
        4. Exclamation marks in professional text
        """
        flags = []
        text_lower = text.lower()

        # Check banned words (with lemma matching)
        for word in BANNED_WORDS:
            pattern = _build_word_pattern(word)
            for match in pattern.finditer(text):
                flags.append(HumanizerFlag(
                    text=match.group(),
                    category="banned_word",
                    suggestion=f'Remove or replace "{match.group()}"',
                    position=match.start(),
                ))

        # Check banned phrases (case-insensitive substring match)
        for phrase in BANNED_PHRASES:
            if phrase.lower() in text_lower:
                pos = text_lower.find(phrase.lower())
                flags.append(HumanizerFlag(
                    text=phrase,
                    category="filler",
                    suggestion=f'Remove "{phrase}"',
                    position=pos,
                ))

        # Check consecutive "I"-starting sentences
        sentences = _split_sentences(text)
        i_streak = 0
        for i, sent in enumerate(sentences):
            stripped = sent.strip()
            if stripped.lower().startswith("i ") or stripped.lower().startswith("i'"):
                i_streak += 1
                if i_streak > MAX_CONSECUTIVE_I_STARTS:
                    snippet = stripped[:60]
                    pos = text.find(snippet) if snippet in text else 0
                    flags.append(HumanizerFlag(
                        text=snippet,
                        category="cadence",
                        suggestion="Vary sentence structure — too many 'I' starts consecutively",
                        position=pos,
                    ))
            else:
                i_streak = 0

        # Check exclamation marks in professional modes (resume, cover_note)
        if text.count("!") > 0:
            for m in re.finditer(r'!', text):
                flags.append(HumanizerFlag(
                    text="!",
                    category="filler",
                    suggestion="Remove exclamation mark from professional communication",
                    position=m.start(),
                ))

        return flags

    # ─── Phase 2: Recruiter Realism Check (DETERMINISTIC) ────────────────────

    def _check_realism(self, text: str, flags: list) -> list:
        """Phase 2: Check recruiter realism (deterministic).

        Detects:
        1. Metrics without baseline or timeframe
        2. Suspiciously round numbers
        3. Inflated ownership language
        4. Unrealistic breadth of expertise claims
        """
        concerns = []

        # Check for percentage metrics without baseline/timeframe context
        metric_pattern = r'(increased|improved|reduced|grew|boosted|cut|decreased|grew)\s+\w+\s+by\s+\d+%'
        for match in re.finditer(metric_pattern, text, re.IGNORECASE):
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 80)
            context_window = text[start:end]

            # Look for baseline indicators
            has_context = re.search(
                r'(from|baseline|over|within|across|during|compared\s+to|relative\s+to|in\s+\d{4}|over\s+\d+\s+(month|quarter|year|week))',
                context_window, re.IGNORECASE
            )
            if not has_context:
                concerns.append({
                    "claim": match.group(),
                    "risk": "medium",
                    "reason": "Metric without baseline or timeframe",
                    "suggested_fix": f"Add baseline or timeframe to '{match.group()}'",
                })

        # Check for suspiciously round, unsupported absolute numbers
        # e.g. "saved $2M" or "processed 1M records" without context
        round_metric_pattern = r'(saved|generated|processed|handled|managed|delivered)\s+\$?\d+[KMB]\b'
        for match in re.finditer(round_metric_pattern, text, re.IGNORECASE):
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 60)
            context_window = text[start:end]
            has_context = re.search(
                r'(over|within|across|during|annually|per\s+\w+|monthly|quarterly|by\s+replacing|using|through)',
                context_window, re.IGNORECASE
            )
            if not has_context:
                concerns.append({
                    "claim": match.group(),
                    "risk": "low",
                    "reason": "Round metric without operational context",
                    "suggested_fix": f"Add operational context to '{match.group()}'",
                })

        # Check for inflated ownership: "led" used repeatedly for what might be contribution
        # Count "led" occurrences — more than 3 in a single document raises flags
        led_matches = list(re.finditer(r'\bled\b', text, re.IGNORECASE))
        if len(led_matches) > 3:
            concerns.append({
                "claim": f"'led' appears {len(led_matches)} times",
                "risk": "low",
                "reason": "Overuse of 'led' can signal inflated ownership",
                "suggested_fix": "Vary with 'built', 'designed', 'managed', or 'co-led' as appropriate",
            })

        # Check for unrealistic breadth: "expert in" many unrelated domains
        expert_matches = list(re.finditer(
            r'\b(expert(?:ise)?\s+in|proficient\s+in|mastery\s+of|deep\s+knowledge\s+of)\s+([^,.]+)',
            text, re.IGNORECASE
        ))
        if len(expert_matches) > 3:
            domains = [m.group(2).strip() for m in expert_matches]
            concerns.append({
                "claim": f"Expertise claimed in {len(expert_matches)} domains: {', '.join(domains[:4])}",
                "risk": "medium",
                "reason": "Too many deep-expertise claims raises credibility risk",
                "suggested_fix": "Focus on 1-2 areas of genuine depth; describe others as 'experience with' rather than 'expertise in'",
            })

        return concerns

    # ─── Phase 3: Surgical Humanize ──────────────────────────────────────────

    def _surgical_humanize(self, text: str, flags: list, mode: str) -> str:
        """Phase 3: Surgical rewrite of flagged portions.

        If LLM is available, sends flags + text for minimal LLM rewrite.
        Otherwise, falls back to deterministic banned-word removal.
        """
        if not flags:
            return text

        if mode == "resume":
            return self._deterministic_clean(text, flags)

        if self.llm is not None:
            return self._llm_surgical_humanize(text, flags)
        else:
            return self._deterministic_clean(text, flags)

    def _llm_surgical_humanize(self, text: str, flags: list) -> str:
        """LLM-based surgical rewrite — minimal, targeted changes only."""
        prompt_lines = [f"Text:\n{text}\n\nFlags to fix:"]
        for f in flags[:20]:  # Cap at 20 flags to avoid overwhelming the prompt
            prompt_lines.append(f"- [{f.category}] {f.text}: {f.suggestion}")
        prompt = "\n".join(prompt_lines)

        try:
            response = self.llm.complete_json(SURGICAL_HUMANIZE_SYSTEM, prompt)
            result = response.get("humanized_text", text)
            # Safety: if LLM returns empty or dramatically shorter text, fall back
            if not result or len(result) < len(text) * 0.3:
                return text
            return result
        except Exception:
            return text  # Fallback: return unchanged

    def _deterministic_clean(self, text: str, flags: list) -> str:
        """Deterministic fallback: remove/replace banned words and phrases.

        Preserves markdown links, metrics, and chronology.
        """
        result = text

        # Process flags in reverse position order to preserve offsets
        sorted_flags = sorted(flags, key=lambda f: f.position, reverse=True)

        for flag in sorted_flags:
            if flag.category == "banned_word":
                replacement = BANNED_WORD_REPLACEMENTS.get(flag.text.lower(), "")
                if replacement:
                    # Replace with alternative
                    result = result[:flag.position] + replacement + result[flag.position + len(flag.text):]
                else:
                    # Remove the word but clean up whitespace
                    result = result[:flag.position] + result[flag.position + len(flag.text):]
                    result = _clean_double_spaces(result)
            elif flag.category == "filler":
                # Remove banished phrases
                phrase_text = flag.text
                pos = flag.position
                if pos < len(result) and result[pos:pos + len(phrase_text)].lower() == phrase_text.lower():
                    result = result[:pos] + result[pos + len(phrase_text):]
                    result = _clean_double_spaces(result)

        # Strip leading/trailing whitespace and normalize newlines
        result = result.strip()
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = re.sub(r' {2,}', ' ', result)

        return result

    # ─── Phase 4: Tone Adaptation ────────────────────────────────────────────

    def _adapt_tone(self, text: str, context: dict, mode: str) -> str:
        """Phase 4: Adapt tone to company type and mode.

        If LLM is available and company_type is non-default, uses LLM.
        Otherwise, applies deterministic tone rules.
        """
        company_type = context.get("company_type", "default")
        tone = context.get("tone", "")

        if mode == "resume":
            return text

        # Normalize company_type
        if company_type not in TONE_PROFILES:
            company_type = "default"

        # Use LLM for tone adaptation if available and there's a specific target
        if self.llm is not None and (company_type != "default" or tone):
            return self._llm_adapt_tone(text, company_type, tone)
        else:
            return self._deterministic_tone_adapt(text, company_type, mode)

    def _llm_adapt_tone(self, text: str, company_type: str, tone: str) -> str:
        """LLM-based tone adaptation."""
        prompt_text = TONE_ADAPTER_SYSTEM.format(
            tone=tone or TONE_PROFILES.get(company_type, TONE_PROFILES["default"])["formality"],
            company_type=company_type,
        )
        try:
            response = self.llm.complete_json(prompt_text, f"Text:\n{text}")
            result = response.get("adapted_text", text)
            if not result or len(result) < len(text) * 0.3:
                return text
            return result
        except Exception:
            return text

    def _deterministic_tone_adapt(self, text: str, company_type: str, mode: str) -> str:
        """Deterministic tone rules based on TONE_PROFILES.

        Applies:
        - Sentence length caps
        - Basic formality adjustments
        """
        profile = TONE_PROFILES.get(company_type, TONE_PROFILES["default"])
        max_len = profile["max_sentence_length"]
        result = text

        # Apply max sentence length by splitting overly long sentences
        sentences = _split_sentences(result)
        adjusted = []
        for sent in sentences:
            words = sent.split()
            if len(words) > max_len:
                # Split at the nearest conjunction or comma near the midpoint
                mid = len(words) // 2
                # Look for a split point near the middle
                split_point = None
                for j in range(mid, min(mid + 10, len(words))):
                    if words[j].rstrip(".,;:") in ("and", "but", "or", "while", "where", "which"):
                        split_point = j + 1
                        break
                if split_point is None:
                    # Try comma split
                    for j in range(mid, min(mid + 10, len(words))):
                        if words[j].endswith(","):
                            split_point = j + 1
                            break
                if split_point:
                    adjusted.append(" ".join(words[:split_point]).rstrip(",") + ".")
                    second = " ".join(words[split_point:])
                    if second and not second.endswith((".", "!", "?")):
                        second += "."
                    adjusted.append(second[0].upper() + second[1:] if second else "")
                else:
                    adjusted.append(sent)
            else:
                adjusted.append(sent)

        # Preserve paragraph breaks — split by double newline, process each paragraph,
        # then rejoin with double newlines
        paragraphs = text.split("\n\n")
        processed = []
        for para in paragraphs:
            if not para.strip():
                processed.append(para)
                continue
            sentences_in_para = _split_sentences(para)
            adjusted_para = []
            for sent in sentences_in_para:
                words = sent.split()
                if len(words) > max_len:
                    mid = len(words) // 2
                    split_point = None
                    for j in range(mid, min(mid + 10, len(words))):
                        if words[j].rstrip(".,;:") in ("and", "but", "or", "while", "where", "which"):
                            split_point = j + 1
                            break
                    if split_point is None:
                        for j in range(mid, min(mid + 10, len(words))):
                            if words[j].endswith(","):
                                split_point = j + 1
                                break
                    if split_point:
                        adjusted_para.append(" ".join(words[:split_point]).rstrip(",") + ".")
                        second = " ".join(words[split_point:])
                        if second and not second.endswith((".", "!", "?")):
                            second += "."
                        adjusted_para.append(second[0].upper() + second[1:] if second else "")
                    else:
                        adjusted_para.append(sent)
                else:
                    adjusted_para.append(sent)
            processed.append(" ".join(adjusted_para))
        return "\n\n".join(processed)


    # ─── Phase 5: Output Sanitization (DETERMINISTIC) ────────────────────────

    def _sanitize_output(self, text: str) -> str:
        """Phase 5: Sanitize final output (deterministic).

        Runs AFTER the Humanizer's LLM phases, so the LLM cannot
        re-introduce artifacts that were stripped earlier.

        Handles:
        - Smart quotes → straight quotes
        - Non-breaking spaces → regular spaces
        - Zero-width characters
        - Normalize excessive newlines
        - Flag (but do not strip) em dashes — recorded in result
        """
        result = text

        # Smart quotes → straight quotes
        result = result.replace('“', '"')  # left double
        result = result.replace('”', '"')  # right double
        result = result.replace('‘', "'")  # left single
        result = result.replace('’', "'")  # right single
        result = result.replace('«', '"')  # left-pointing double angle
        result = result.replace('»', '"')  # right-pointing double angle

        # Non-breaking spaces → regular spaces
        result = result.replace(' ', ' ')
        result = result.replace(' ', ' ')  # narrow non-breaking space

        # Zero-width characters
        result = result.replace('​', '')   # zero-width space
        result = result.replace('‌', '')   # zero-width non-joiner
        result = result.replace('‍', '')   # zero-width joiner
        result = result.replace('﻿', '')   # BOM / zero-width no-break space

        # Normalize excessive newlines (max 2 consecutive)
        result = re.sub(r'\n{3,}', '\n\n', result)

        # Normalize trailing whitespace on each line
        result = '\n'.join(line.rstrip() for line in result.split('\n'))

        # Strip leading/trailing whitespace
        result = result.strip()

        return result

# ─── Utility helpers ─────────────────────────────────────────────────────────────

def _build_word_pattern(word: str) -> re.Pattern:
    """Build a regex that matches a word and its common English conjugations.

    Handles:
    - Exact match: "leverage"
    - Past tense (word+d): "leveraged"
    - Present participle (stem+ing): "leveraging"  (drops 'e')
    - Past participle (stem+ed): "leveraged"      (drops 'e')
    - Plural (word+s): "leverages"
    - Noun form (word+ment): "leveragement"

    For words NOT ending in 'e', uses simpler suffix matching.
    """
    escaped = re.escape(word)
    if word.endswith('e'):
        stem = re.escape(word[:-1])
        # Word forms: word, word+d, word+s, word+ment
        # Stem forms: stem+ing, stem+ed
        pattern = (
            r'\b(?:' + escaped + r'(?:d|s|ment)?|'
            + stem + r'(?:ing|ed))\b'
        )
    else:
        pattern = r'\b' + escaped + r'(?:ing|ed|s|ment|d)?\b'
    return re.compile(pattern, re.IGNORECASE)


def _split_sentences(text: str) -> list:
    """Split text into sentences, preserving markdown formatting."""
    # Split on sentence boundaries: . ! ? followed by space and capital letter or newline
    pattern = r'(?<=[.!?])\s+(?=[A-Z#\n])'
    parts = re.split(pattern, text)
    # Re-join markdown headings that got split (## Something)
    return [p.strip() for p in parts if p.strip()]


def _clean_double_spaces(text: str) -> str:
    """Remove double spaces without touching intentional markdown formatting."""
    return re.sub(r'  +', ' ', text)


def _markdown_structure_safe(original: str, candidate: str) -> tuple[bool, list[str]]:
    """Check that resume humanization did not mutate Markdown structure."""
    issues: list[str] = []

    original_bullets = _count_markdown_bullets(original)
    candidate_bullets = _count_markdown_bullets(candidate)
    if candidate_bullets < original_bullets:
        issues.append(f"bullet_count_dropped:{original_bullets}->{candidate_bullets}")

    original_headings = _count_markdown_headings(original)
    candidate_headings = _count_markdown_headings(candidate)
    if candidate_headings < original_headings:
        issues.append(f"heading_count_dropped:{original_headings}->{candidate_headings}")

    if re.search(r"\.\s+[-*]\s+[A-Z0-9]", candidate or ""):
        issues.append("collapsed_bullet_marker")

    return not issues, issues


def _count_markdown_bullets(text: str) -> int:
    return len(re.findall(r"(?m)^\s*[-*]\s+\S", text or ""))


def _count_markdown_headings(text: str) -> int:
    return len(re.findall(r"(?m)^\s{0,3}#{1,6}\s+\S", text or ""))
