import re
from typing import List, Dict, Any
from careerloop.council.models import (
    CanonicalResume, 
    ResumeSection, 
    VisibilityClass, 
    PreservationContract,
    SectionRewrites,
    QualityReport
)

class ResumeCompiler:
    """
    Deterministic logic for parsing, contract building, and assembling resumes.
    """

    @staticmethod
    def parse_markdown(text: str) -> CanonicalResume:
        """
        System 1: Document Parser
        Splits markdown into logical sections based on headers.
        """
        sections = []
        # Match headers like # Header, ## Header, ### Header
        pattern = r"(^#+\s+.*$)"
        parts = re.split(pattern, text, flags=re.MULTILINE)
        
        # If there's text before the first header (e.g. contact info)
        if parts and not re.match(pattern, parts[0]):
            intro = parts.pop(0).strip()
            if intro:
                sections.append(ResumeSection(
                    section_id="intro",
                    section_title="Intro/Contact",
                    normalized_type="contact",
                    visibility_class=VisibilityClass.PUBLIC,
                    raw_text=intro,
                    original_order=0
                ))

        current_order = len(sections)
        for i in range(0, len(parts), 2):
            header = parts[i].strip()
            content = parts[i+1].strip() if i+1 < len(parts) else ""
            
            section_title = re.sub(r"^#+\s+", "", header)
            section_id = section_title.lower().replace(" ", "_")
            
            # Classification logic
            normalized_type, visibility = ResumeCompiler._classify_section(section_title, content)
            
            sections.append(ResumeSection(
                section_id=section_id,
                section_title=section_title,
                normalized_type=normalized_type,
                visibility_class=visibility,
                raw_text=content,
                original_order=current_order,
                links=re.findall(r"\[.*?\]\((.*?)\)", content)
            ))
            current_order += 1
            
        return CanonicalResume(sections=sections)

    @staticmethod
    def _classify_section(title: str, content: str) -> tuple:
        title_lower = title.lower()
        
        private_keywords = ["deal-breaker", "target role", "salary", "preference", "internal", "frustration", "constraint"]
        public_keywords = ["experience", "summary", "profile", "skill", "education", "project", "achievement", "contact", "about", "thesis", "research", "publication", "language", "certification"]
        
        if any(k in title_lower for k in private_keywords):
            return "private_metadata", VisibilityClass.PRIVATE
        
        for k in public_keywords:
            if k in title_lower:
                return k, VisibilityClass.PUBLIC
                
        return "unknown", VisibilityClass.UNKNOWN

    @staticmethod
    def build_contract(resume: CanonicalResume, profile: dict) -> PreservationContract:
        """
        System 2: Document Preservation + Structure Contract
        """
        required = []
        exclude = []
        unknown = []
        
        for section in resume.sections:
            if section.visibility_class == VisibilityClass.PUBLIC:
                # Essential sections that should never be dropped
                if section.normalized_type in ["contact", "education", "experience"]:
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
            link_preservation_rules={"all": "MUST_SURVIVE"}
        )

    @staticmethod
    def assemble(resume: CanonicalResume, rewrites: SectionRewrites, contract: PreservationContract) -> str:
        """
        System 8: Safe Assembler (Deterministic)
        """
        output_parts = []
        
        # Sort sections by original order or following ordering rules
        sorted_sections = sorted(resume.sections, key=lambda s: s.original_order)
        
        for section in sorted_sections:
            if section.section_id in contract.sections_to_exclude:
                continue
                
            # Header
            if section.section_id != "intro":
                output_parts.append(f"## {section.section_title}\n")
            
            # Content
            if section.section_id in rewrites.rewrites:
                output_parts.append(rewrites.rewrites[section.section_id].rewritten_text)
            else:
                output_parts.append(section.raw_text)
                
            output_parts.append("\n")
            
        return "\n".join(output_parts).strip()

    @staticmethod
    def generate_quality_report(resume: CanonicalResume, rewrites: SectionRewrites, contract: PreservationContract, claims_not_allowed: List[str] = None) -> QualityReport:
        changed = []
        unchanged = []
        risks = []
        needs_user_review = []
        
        if claims_not_allowed is None:
            claims_not_allowed = []
            
        for section in resume.sections:
            if section.section_id in contract.sections_to_exclude:
                continue
            if section.section_id in rewrites.rewrites:
                rewrite_obj = rewrites.rewrites[section.section_id]
                changed.append(f"Section '{section.section_title}' was rewritten ({rewrite_obj.change_type})")
                if rewrite_obj.change_type == "REWRITE":
                    needs_user_review.append(f"Section '{section.section_title}' was completely rewritten.")
                if getattr(rewrite_obj, "risk_level", "") == "high":
                    risks.append(f"High risk rewrite in '{section.section_title}'")
            else:
                unchanged.append(section.section_title)
                
        for claim in claims_not_allowed:
            needs_user_review.append(f"Verify claim was not made: '{claim}'")
            
        confidence = round(len(rewrites.rewrites) / max(len(resume.sections), 1), 2)
                
        return QualityReport(
            what_changed=changed,
            what_did_not_change=unchanged,
            needs_user_review=needs_user_review,
            risks=risks,
            confidence=confidence
        )
