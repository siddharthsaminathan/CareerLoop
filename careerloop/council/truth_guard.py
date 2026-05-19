"""
Semantic Truth Guard — validates claims against evidence.
Classifies claims by risk level, applies surgical repairs.
NEVER deletes text blindly.

Deterministic: no LLM dependency. Uses regex extraction,
token-overlap fuzzy matching, and pattern-based repair.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Claim:
    """A single claim extracted from rewritten text."""
    text: str
    risk_level: str = "UNCLASSIFIED"
    # VERIFIED, WEAK, UNSUPPORTED, EXAGGERATED, FABRICATED
    claim_type: str = ""
    # year_experience, skill_assertion, ownership, quantified_achievement, percentage
    start_pos: int = 0
    end_pos: int = 0
    evidence_match: Optional[str] = None
    repair_suggestion: Optional[str] = None
    confidence: float = 0.0


@dataclass
class TruthGuardReport:
    """Aggregate report for all claims in a validation run."""
    total_claims: int = 0
    verified: int = 0
    weak: int = 0
    unsupported: int = 0
    exaggerated: int = 0
    fabricated: int = 0
    claims: list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# TruthGuard
# ═══════════════════════════════════════════════════════════════════════════════

class TruthGuard:
    """Semantic claim validator and repairer.

    Deterministic pipeline:
      1. Extract claims from text via regex patterns
      2. Classify each claim against UserTruth evidence
      3. Report — which claims are safe, which need repair
      4. Repair — surgical substitution, never blind deletion
    """

    # ── Thresholds ──────────────────────────────────────────────────
    NOT_ALLOWED_THRESHOLD = 0.35   # token overlap to flag as fabricated
    WEAK_THRESHOLD = 0.25          # token overlap to flag as weak
    YEAR_EXAGGERATION_MARGIN = 2   # years beyond total to call EXAGGERATED vs FABRICATED

    # ── Regex patterns for claim extraction ─────────────────────────
    YEAR_PATTERN = re.compile(
        r"""(\d+[+]*)                     # digit(s) with optional '+'
            \s*(years?|yrs?)              # "year"/"years"/"yr"/"yrs"
            \s+
            (?:of\s+)?                    # optional "of "
            (?:experience(?:\s+in\s+[^\n]+?)?   # "experience in <domain>" or "experience"
               |in\s+[^\n]+?                    # "in <domain>"
               |[^\n]+?)                         # direct domain after "of"
            (?=\s*[,.;]|$|\s+(?:and|or|but|with|across|including|to|from|for|at|on|by|as|over|under|through|via|using))""",
        re.IGNORECASE | re.VERBOSE,
    )

    PERCENT_PATTERN = re.compile(
        r"""(\d+[.]?\d*\s*%)            # percentage like "40%"
            \s*(improvement|increase|reduction|faster|better|
                growth|savings|boost|cut|gain|lift|decrease)""",
        re.IGNORECASE | re.VERBOSE,
    )

    SKILL_ASSERT_PATTERN = re.compile(
        r"""\b(expert|proficient|skilled|specialist|advanced|
               master|deep\s+expertise|strong\s+background)
            \s+(in|with|knowledge\s+of)\s+
            ([^\n]+?)                                  # skill domain (no newlines)
            (?=\s*[,.;]|$|\s+(?:and|or|but|with|across|including|to|from|for|at|on|by|as|over|under|through|via|using))""",
        re.IGNORECASE | re.VERBOSE,
    )

    OWNERSHIP_PATTERN = re.compile(
        r"""(?<![-\w])(led|managed|owned|directed|headed|architected|
               spearheaded|orchestrated|built|created)
            \s+([^\n]+?)                               # what was led/built/etc. (no newlines)
            (?=\s*[,.;]|$|\s+(?:and|or|but|for|at|across|to|from|with|on|by|as|over|under|through|via|using))""",
        re.IGNORECASE | re.VERBOSE,
    )

    QUANTIFIED_PATTERN = re.compile(
        r"""\b(generated|saved|delivered|drove|secured|won|captured)
            \s+\$?\d+[KMB]?\s*[^\n]*?
            (?=\s*[,.;]|$|\s+(?:and|or|but|for|at|across|to|from|with|on|by|as|over|under|through|via|using))""",
        re.IGNORECASE | re.VERBOSE,
    )

    LEAD_IN_PATTERN = re.compile(
        r"""\b(over|more\s+than|nearly|approximately|about|
               around|close\s+to|upwards\s+of)\s+\d+""",
        re.IGNORECASE | re.VERBOSE,
    )

    # ───────────────────────────────────────────────────────────────
    # Token Overlap
    # ───────────────────────────────────────────────────────────────

    @staticmethod
    def _token_overlap(text_a: str, text_b: str) -> float:
        """Return Jaccard similarity of normalized word tokens (0.0-1.0).

        Normalizes: lowercases, strips number-plus (7+ → 7),
        removes punctuation, splits on whitespace.
        """
        def _normalize(s: str) -> set:
            s = s.lower()
            # Normalize "7+" → "7" for number comparison
            s = re.sub(r'(\d+)\+', r'\1', s)
            # Replace punctuation (not / or # or &) with spaces
            s = re.sub(r'[.,;:!?()\[\]{}"\'`]', ' ', s)
            parts = s.split()
            return set(p for p in parts if p)

        tokens_a = _normalize(text_a)
        tokens_b = _normalize(text_b)
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    # ───────────────────────────────────────────────────────────────
    # Claim Extraction
    # ───────────────────────────────────────────────────────────────

    def _extract_claims(self, text: str) -> List[Claim]:
        """Extract all claim-like statements from text with byte positions."""
        claims: List[Claim] = []

        # Year experience claims
        for m in self.YEAR_PATTERN.finditer(text):
            claims.append(Claim(
                text=m.group(0).strip(),
                risk_level="UNCLASSIFIED",
                claim_type="year_experience",
                start_pos=m.start(),
                end_pos=m.end(),
            ))

        # Percentage claims
        for m in self.PERCENT_PATTERN.finditer(text):
            claims.append(Claim(
                text=m.group(0).strip(),
                risk_level="UNCLASSIFIED",
                claim_type="percentage",
                start_pos=m.start(),
                end_pos=m.end(),
            ))

        # Skill assertions
        for m in self.SKILL_ASSERT_PATTERN.finditer(text):
            claims.append(Claim(
                text=m.group(0).strip(),
                risk_level="UNCLASSIFIED",
                claim_type="skill_assertion",
                start_pos=m.start(),
                end_pos=m.end(),
            ))

        # Ownership claims
        for m in self.OWNERSHIP_PATTERN.finditer(text):
            claims.append(Claim(
                text=m.group(0).strip(),
                risk_level="UNCLASSIFIED",
                claim_type="ownership",
                start_pos=m.start(),
                end_pos=m.end(),
            ))

        # Quantified achievement claims
        for m in self.QUANTIFIED_PATTERN.finditer(text):
            claims.append(Claim(
                text=m.group(0).strip(),
                risk_level="UNCLASSIFIED",
                claim_type="quantified_achievement",
                start_pos=m.start(),
                end_pos=m.end(),
            ))

        # Sort by position in text
        claims.sort(key=lambda c: c.start_pos)
        return claims

    # ───────────────────────────────────────────────────────────────
    # Classification
    # ───────────────────────────────────────────────────────────────

    def _classify_claim(
        self,
        claim: Claim,
        user_truth: dict,
        evidence_bank: dict,
        claims_not_allowed: List[str],
        claims_allowed: List[str],
    ) -> Claim:
        """Classify a single claim's risk level against evidence."""

        # ── Tier 1: Check against claims_not_allowed ────────────
        for disallowed in claims_not_allowed:
            if not disallowed:
                continue
            overlap = self._token_overlap(claim.text, disallowed)
            if overlap >= self.NOT_ALLOWED_THRESHOLD:
                claim.risk_level = "FABRICATED"
                claim.confidence = overlap
                claim.evidence_match = (
                    f"Matches disallowed claim: '{disallowed}'"
                )
                return claim

        # ── Tier 2: Type-specific classification ────────────────
        if claim.claim_type == "year_experience":
            self._classify_year_claim(claim, user_truth)
        elif claim.claim_type == "skill_assertion":
            self._classify_skill_claim(claim, user_truth)
        elif claim.claim_type in (
            "ownership", "quantified_achievement", "percentage"
        ):
            self._classify_evidence_claim(
                claim, user_truth, evidence_bank, claims_allowed
            )
        else:
            self._classify_generic(claim, claims_allowed)

        return claim

    def _classify_year_claim(self, claim: Claim, user_truth: dict):
        """Classify year-experience claims against total_years_experience."""
        total_years = user_truth.get("total_years_experience", 0)
        year_match = re.search(r'(\d+)', claim.text)
        if not year_match:
            claim.risk_level = "UNSUPPORTED"
            claim.confidence = 0.0
            return

        claimed_years = int(year_match.group(1))

        # Detect "X+" or "over X" modifiers
        has_plus = (
            '+' in claim.text
            or bool(self.LEAD_IN_PATTERN.search(claim.text))
        )

        if claimed_years <= total_years and not has_plus:
            claim.risk_level = "VERIFIED"
            claim.confidence = 0.9
            claim.evidence_match = (
                f"Confirmed: total_years_experience = {total_years}"
            )
        elif claimed_years <= total_years and has_plus:
            # "X+ years" when total >= X — technically true, puffery
            claim.risk_level = "WEAK"
            claim.confidence = 0.6
            claim.evidence_match = (
                f"Partially supported: actual total = {total_years}, "
                f"claimed {claimed_years}+"
            )
        elif claimed_years > total_years:
            delta = claimed_years - total_years
            if delta <= self.YEAR_EXAGGERATION_MARGIN:
                claim.risk_level = "EXAGGERATED"
                claim.confidence = max(0.1, 0.5 - (delta * 0.15))
                claim.repair_suggestion = self._format_year_sub(
                    claim.text, int(total_years)
                )
            else:
                claim.risk_level = "FABRICATED"
                claim.confidence = 0.0
                claim.repair_suggestion = self._format_year_sub(
                    claim.text, int(total_years)
                )
        else:
            claim.risk_level = "WEAK"
            claim.confidence = 0.3

    def _classify_skill_claim(self, claim: Claim, user_truth: dict):
        """Classify skill assertion claims against confirmed/weak skills."""
        confirmed_skills = user_truth.get("confirmed_skills", [])
        weak_skills = user_truth.get("weak_skills", [])

        # Normalize confirmed skill names from List[Dict[str, str]]
        confirmed_names: set = set()
        for skill in confirmed_skills:
            if isinstance(skill, dict):
                name = skill.get("name") or skill.get("skill") or ""
                if name:
                    confirmed_names.add(name.lower())
            elif isinstance(skill, str):
                confirmed_names.add(skill.lower())

        weak_names = set(
            s.lower() for s in weak_skills if isinstance(s, str) and s
        )

        # Extract the skill domain from the claim
        # e.g., "expert in Python / Django" → skill domain is "python / django"
        skill_domain = claim.text.lower()
        for prefix in [
            "expert in ", "expert with ", "proficient in ", "proficient with ",
            "skilled in ", "skilled with ", "specialist in ",
            "advanced knowledge of ", "master of ", "strong background in ",
            "deep expertise in ",
        ]:
            if skill_domain.startswith(prefix):
                skill_domain = skill_domain[len(prefix):]
                break

        skill_tokens = set(skill_domain.split())

        # ── Check confirmed skills ──
        best_overlap = 0.0
        best_name = None
        for cname in confirmed_names:
            cname_tokens = set(cname.lower().split())
            overlap = (
                len(skill_tokens & cname_tokens)
                / max(1, len(skill_tokens))
            )
            if overlap > best_overlap:
                best_overlap = overlap
                best_name = cname

        if best_overlap >= 0.5:
            claim.risk_level = "VERIFIED"
            claim.confidence = best_overlap
            claim.evidence_match = f"Confirmed skill: {best_name}"
            return

        # ── Check weak skills ──
        best_weak = 0.0
        best_weak_name = None
        for wname in weak_names:
            wname_tokens = set(wname.lower().split())
            overlap = (
                len(skill_tokens & wname_tokens)
                / max(1, len(skill_tokens))
            )
            if overlap > best_weak:
                best_weak = overlap
                best_weak_name = wname

        if best_weak >= 0.3:
            claim.risk_level = "WEAK"
            claim.confidence = best_weak * 0.6
            claim.evidence_match = f"Weak skill match: {best_weak_name}"
            claim.repair_suggestion = self._downgrade_qualifier(claim.text)
            return

        # ── Partial confirmed match with inflated language ──
        if best_overlap >= 0.3:
            claim.risk_level = "EXAGGERATED"
            claim.confidence = 0.3
            claim.evidence_match = (
                f"Partial skill match: {best_name} (language inflated)"
            )
            claim.repair_suggestion = self._downgrade_qualifier(claim.text)
            return

        # ── No match at all ──
        claim.risk_level = "UNSUPPORTED"
        claim.confidence = 0.0

    def _classify_evidence_claim(
        self,
        claim: Claim,
        user_truth: dict,
        evidence_bank: dict,
        claims_allowed: List[str],
    ):
        """Classify ownership/achievement claims against evidence bank."""
        # Check claims_allowed first
        for allowed in claims_allowed:
            if not allowed:
                continue
            overlap = self._token_overlap(claim.text, allowed)
            if overlap >= 0.4:
                claim.risk_level = "VERIFIED"
                claim.confidence = overlap
                claim.evidence_match = (
                    f"Matches allowed claim: '{allowed}'"
                )
                return

        # Check evidence bank
        all_evidence_text = " ".join(
            ev for evlist in evidence_bank.values()
            if isinstance(evlist, list)
            for ev in evlist
            if ev and isinstance(ev, str)
        ).lower()

        for evidence_key, evidence_values in evidence_bank.items():
            if not isinstance(evidence_values, list):
                continue
            for ev in evidence_values:
                if not ev or not isinstance(ev, str):
                    continue
                overlap = self._token_overlap(claim.text, ev)
                if overlap >= 0.3:
                    claim.risk_level = "WEAK"
                    claim.confidence = overlap * 0.7
                    claim.evidence_match = (
                        f"Partial evidence match in '{evidence_key}'"
                    )
                    return

        # Number-presence check: if every specific number/percentage in the
        # claim appears somewhere in the evidence bank, treat as WEAK rather
        # than UNSUPPORTED. Short claims like "10% lift" have low Jaccard
        # against long evidence strings but the metric is still grounded.
        numbers_in_claim = re.findall(r'\d+[.,]?\d*\s*%?', claim.text)
        if numbers_in_claim:
            matched = all(
                num.replace(' ', '').lower() in all_evidence_text
                for num in numbers_in_claim
                if num.strip()
            )
            if matched:
                claim.risk_level = "WEAK"
                claim.confidence = 0.4
                claim.evidence_match = (
                    "Numbers present in evidence bank — claim likely grounded"
                )
                return

        # No evidence found
        claim.risk_level = "UNSUPPORTED"
        claim.confidence = 0.0

    def _classify_generic(
        self, claim: Claim, claims_allowed: List[str]
    ):
        """Generic fallback classification against allowed list."""
        for allowed in claims_allowed:
            if not allowed:
                continue
            overlap = self._token_overlap(claim.text, allowed)
            if overlap >= 0.3:
                claim.risk_level = "VERIFIED"
                claim.confidence = overlap
                claim.evidence_match = (
                    f"Matches allowed claim: '{allowed}'"
                )
                return
        claim.risk_level = "UNSUPPORTED"
        claim.confidence = 0.0

    # ───────────────────────────────────────────────────────────────
    # Repair Helpers (deterministic, string-based)
    # ───────────────────────────────────────────────────────────────

    @staticmethod
    def _format_year_sub(original: str, actual_years: int) -> str:
        """Build a year-claim replacement using actual years."""
        # Preserve the domain part: "7+ years of AI/ML experience" → keep "of AI/ML experience"
        domain_match = re.search(
            r'(?:of\s+)?(?:experience\s+)?(in\s+.+)',
            original, re.IGNORECASE,
        )
        domain = domain_match.group(1) if domain_match else ""
        if domain:
            return f"over {actual_years} years {domain}"
        return f"over {actual_years} years of experience"

    @staticmethod
    def _downgrade_qualifier(text: str) -> str:
        """Downgrade inflated skill qualifiers to honest ones.

        'Expert in Python' → 'Experienced with Python'
        'master of React' → 'strong in React'
        """
        qualifier_map = {
            'expert':           'experienced',
            'Expert':           'Experienced',
            'proficient':       'skilled',
            'Proficient':       'Skilled',
            'master':           'strong',
            'Master':           'Strong',
            'specialist':       'practitioner',
            'Specialist':       'Practitioner',
            'advanced':         'solid',
            'Advanced':         'Solid',
            'deep expertise':   'experience',
            'Deep expertise':   'Experience',
            'strong background': 'background',
            'Strong background': 'Background',
        }
        for inflated, toned in qualifier_map.items():
            if inflated in text:
                return text.replace(inflated, toned, 1)
        return text

    @staticmethod
    def _minimize_claim(original: str) -> str:
        """Reduce a claim to its safest minimal grammatical form.

        'led a team of 20 engineers' → 'contributed to team efforts'
        'generated $2M in revenue' → 'contributed to revenue initiatives'
        """
        verb_map = {
            'led':           'contributed to',
            'Led':           'Contributed to',
            'managed':       'supported',
            'Managed':       'Supported',
            'owned':         'contributed to',
            'Owned':         'Contributed to',
            'directed':      'supported',
            'Directed':      'Supported',
            'architected':   'worked on',
            'Architected':   'Worked on',
            'spearheaded':   'contributed to',
            'Spearheaded':   'Contributed to',
            'orchestrated':  'coordinated',
            'Orchestrated':  'Coordinated',
            'generated':     'contributed to',
            'Generated':     'Contributed to',
            'delivered':     'supported',
            'Delivered':     'Supported',
            'secured':       'worked toward',
            'Secured':       'Worked toward',
            'built':         'contributed to building',
            'Built':         'Contributed to building',
            'created':       'contributed to creating',
            'Created':       'Contributed to creating',
        }
        for strong, weak in verb_map.items():
            if original.startswith(strong + ' ') or original.startswith(strong + '\t'):
                # Replace just the lead verb, keep the rest
                remainder = original[len(strong):]
                return weak + remainder
        return original

    @staticmethod
    def _cleanup_artifacts(text: str) -> str:
        """Clean up whitespace and punctuation artifacts from repairs.

        Never touches markdown links, bullets, or headings.
        """
        # Collapse multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        # Remove space before punctuation (but NOT within markdown links)
        text = re.sub(r'\s+([,.;:!?)])', r'\1', text)
        # Remove doubled punctuation
        text = re.sub(r'([,.;:!?])\1+', r'\1', text)
        # Remove empty bullet lines (bullet with only whitespace)
        text = re.sub(r'^[\t ]*[-*+]\s*$\n?', '', text, flags=re.MULTILINE)
        # Collapse 3+ newlines to 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Strip trailing whitespace per line
        lines = [line.rstrip() for line in text.split('\n')]
        text = '\n'.join(lines)
        return text.strip()

    # ───────────────────────────────────────────────────────────────
    # Public API
    # ───────────────────────────────────────────────────────────────

    def validate(
        self,
        text: str,
        user_truth: dict,
        evidence_bank: dict,
        claims_not_allowed: List[str],
    ) -> List[Claim]:
        """Extract and classify all claims in text. Deterministic."""
        if not text or not text.strip():
            return []

        claims_allowed = (
            user_truth.get("claims_allowed", []) if user_truth else []
        )
        if not isinstance(claims_not_allowed, list):
            claims_not_allowed = []

        claims = self._extract_claims(text)

        for claim in claims:
            self._classify_claim(
                claim,
                user_truth,
                evidence_bank,
                claims_not_allowed,
                claims_allowed,
            )

        return claims

    def repair(self, text: str, claims: List[Claim]) -> str:
        """Apply surgical repairs to flagged claims.

        Works backwards through claims (by position) so that earlier
        replacements don't invalidate later positions.  Never deletes
        — substitutes, qualifies, or tones down.
        """
        if not text or not claims:
            return text

        # Only repair claims that need it
        flagged = [
            c for c in claims
            if c.risk_level in ("UNSUPPORTED", "EXAGGERATED", "FABRICATED")
        ]
        if not flagged:
            return text

        # Sort by position descending — repair from end to start
        flagged.sort(key=lambda c: c.start_pos, reverse=True)

        repaired = text
        for claim in flagged:
            span = self._find_claim_span(repaired, claim)
            if span is None:
                continue

            start, end = span
            original_fragment = repaired[start:end]
            replacement = self._generate_repair(original_fragment, claim)

            if replacement and replacement != original_fragment:
                repaired = (
                    repaired[:start] + replacement + repaired[end:]
                )

        return self._cleanup_artifacts(repaired)

    def _find_claim_span(
        self, text: str, claim: Claim
    ) -> Optional[Tuple[int, int]]:
        """Locate the claim in (possibly already-repaired) text.

        Prefers original positions; falls back to substring search.
        """
        # Try original positions if still coherent
        if (
            claim.start_pos < len(text)
            and claim.end_pos <= len(text)
        ):
            candidate = text[claim.start_pos:claim.end_pos]
            if self._token_overlap(candidate, claim.text) >= 0.4:
                return (claim.start_pos, claim.end_pos)

        # Fallback: case-insensitive substring search
        idx = text.lower().find(claim.text.lower())
        if idx >= 0:
            return (idx, idx + len(claim.text))

        # Loose fallback: search by key tokens
        tokens = [t for t in claim.text.lower().split() if len(t) > 2]
        if len(tokens) >= 3:
            key = ' '.join(tokens[:min(5, len(tokens))])
            idx = text.lower().find(key)
            if idx >= 0:
                end = min(idx + len(claim.text) + 30, len(text))
                return (idx, end)

        return None

    def _generate_repair(self, original: str, claim: Claim) -> str:
        """Produce a grammatically complete replacement for a flagged claim.

        Routes to type-specific repair methods.
        """
        if claim.claim_type == "year_experience":
            return self._repair_year_claim(original, claim)
        elif claim.claim_type == "skill_assertion":
            return self._repair_skill_claim(original, claim)
        elif claim.claim_type in (
            "ownership", "quantified_achievement", "percentage"
        ):
            return self._repair_evidence_claim(original, claim)
        else:
            return self._repair_fallback(original, claim)

    def _repair_year_claim(self, original: str, claim: Claim) -> str:
        """Repair an inflated year-experience claim."""
        year_match = re.search(r'(\d+)([+]*)', original)
        if not year_match:
            return original

        if claim.risk_level == "FABRICATED":
            # Substitute with available evidence or minimize
            if claim.repair_suggestion:
                return claim.repair_suggestion
            # Remove the false number, keep the domain
            without_num = re.sub(
                r'\d+[+]*\s*years?\s*(of\s+)?',
                '', original, count=1,
            ).strip()
            if without_num:
                return f"relevant {without_num}"
            return "relevant experience"

        elif claim.risk_level == "EXAGGERATED":
            if claim.repair_suggestion:
                return claim.repair_suggestion
            # Remove the '+' but keep the number hedged
            repaired = re.sub(r'(\d+)\+', r'nearly \1', original)
            return repaired

        elif claim.risk_level == "UNSUPPORTED":
            # Remove the specific number, hedge the claim
            repaired = re.sub(
                r'\d+[+]*\s*years?\s*',
                '', original, count=1,
            ).strip()
            if repaired:
                return f"significant {repaired}"
            return "significant experience"

        return original

    def _repair_skill_claim(self, original: str, claim: Claim) -> str:
        """Repair an inflated or fabricated skill claim."""
        if claim.risk_level in ("EXAGGERATED", "UNSUPPORTED"):
            # Downgrade the qualifier
            return self._downgrade_qualifier(original)

        elif claim.risk_level == "FABRICATED":
            # Fabricated skill — minimize to safest form
            # Turn "Expert in <X>" into a weaker, truthful statement
            if claim.repair_suggestion:
                return claim.repair_suggestion
            return self._minimize_claim(original)

        return original

    def _repair_evidence_claim(self, original: str, claim: Claim) -> str:
        """Repair an unsupported evidence-based claim.

        Ownership UNSUPPORTED → return original unchanged.
          The evidence bank is LLM-paraphrased so Jaccard misses legitimate
          claims like "Managed PO/PI coordination" vs "Managed PO/PI for 20+
          suppliers at Go Colors".  We log these for user review but NEVER
          mangle CV text that is likely truthful.

        Ownership FABRICATED or EXAGGERATED → minimize (deliberate overreach).

        Quantified / percentage UNSUPPORTED or EXAGGERATED → strip the metric.
        """
        if claim.risk_level == "FABRICATED":
            return self._minimize_claim(original)

        if claim.risk_level == "EXAGGERATED":
            if claim.claim_type == "ownership":
                return self._minimize_claim(original)
            # quantified_achievement / percentage: strip the specific number
            repaired = re.sub(r'\$?\d+[KMB]?\s*', '', original, count=1)
            repaired = re.sub(r'\d+[.]?\d*\s*%\s*', '', repaired, count=1)
            repaired = re.sub(r'\s{2,}', ' ', repaired).strip()
            if not repaired or len(repaired) < 5:
                return self._minimize_claim(original)
            return repaired

        if claim.risk_level == "UNSUPPORTED":
            if claim.claim_type == "ownership":
                # Leave ownership text intact — evidence bank paraphrase mismatch
                # is a false positive.  Caller logs this for user review.
                return original
            # quantified_achievement / percentage: strip unverified metric
            repaired = re.sub(r'\$?\d+[KMB]?\s*', '', original, count=1)
            repaired = re.sub(r'\d+[.]?\d*\s*%\s*', '', repaired, count=1)
            repaired = re.sub(r'\s{2,}', ' ', repaired).strip()
            if not repaired or len(repaired) < 5:
                return original
            return repaired

        return original

    def _repair_fallback(self, original: str, claim: Claim) -> str:
        """Last-resort repair — minimize without destroying grammar."""
        if claim.risk_level == "FABRICATED":
            return self._minimize_claim(original)
        return original

    def generate_report(self, claims: List[Claim]) -> TruthGuardReport:
        """Generate a summary report from classified claims."""
        report = TruthGuardReport()
        report.total_claims = len(claims)
        report.claims = claims

        for claim in claims:
            if claim.risk_level == "VERIFIED":
                report.verified += 1
            elif claim.risk_level == "WEAK":
                report.weak += 1
            elif claim.risk_level == "UNSUPPORTED":
                report.unsupported += 1
            elif claim.risk_level == "EXAGGERATED":
                report.exaggerated += 1
            elif claim.risk_level == "FABRICATED":
                report.fabricated += 1
            # UNCLASSIFIED claims (shouldn't happen) are not counted

        return report
