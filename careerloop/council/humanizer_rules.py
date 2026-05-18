"""Humanizer rules — banned words, phrases, and structural constraints."""

BANNED_WORDS = [
    "passionate", "leverage", "spearheaded", "synergize", "synergy",
    "revolutionize", "disrupt", "disruptive", "game-changer", "best-in-class",
    "cutting-edge", "state-of-the-art", "thought leader", "ninja", "guru", "wizard",
    "rockstar", "hustle", "grind", "deep dive", "unlock", "supercharge",
    "empower", "innovative", "dynamic", "results-driven", "visionary",
    "fast-paced environment", "seasoned", "proven track record",
    "agentic", "autonomous",
]

# Mapping of banned words to context-appropriate alternatives.
# Used by the deterministic fallback in Phase 1.
BANNED_WORD_REPLACEMENTS = {
    "passionate": "focused",
    "leveraging": "using",
    "leverage": "use",
    "spearheaded": "led",
    "synergize": "combine",
    "synergy": "collaboration",
    "revolutionize": "transform",
    "disrupt": "change",
    "disruptive": "novel",
    "innovative": "",   # remove — the thing either is or isn't
    "dynamic": "active",
    "visionary": "strategic",
    "empower": "support",
    "supercharge": "accelerate",
    "unlock": "enable",
    "game-changer": "breakthrough",
    "best-in-class": "top-tier",
    "cutting-edge": "modern",
    "state-of-the-art": "advanced",
    "ninja": "expert",
    "guru": "specialist",
    "wizard": "expert",
    "rockstar": "high-performer",
    "hustle": "focus",
    "grind": "effort",
    "deep dive": "analysis",
    "thought leader": "domain expert",
    "results-driven": "outcome-focused",
    "seasoned": "experienced",
    "proven track record": "track record",
    "fast-paced environment": "fast-moving team",
    "agentic": "AI-driven",
    "autonomous": "self-directed",
}

BANNED_PHRASES = [
    "in this essay I will", "it is important to note",
    "I am writing to express my interest", "as a highly motivated",
    "with a proven track record", "results-driven professional",
    "I believe I am the ideal candidate", "I am confident that",
    "thank you for taking the time", "I look forward to hearing",
    "I am excited to apply", "I am thrilled to",
    "multi-agent", "swarm", "AI revolution",
]

TONE_PROFILES = {
    "startup": {
        "max_sentence_length": 25,
        "salutation": "Hey",
        "contractions": True,
        "formality": "low",
    },
    "growth": {
        "max_sentence_length": 28,
        "salutation": "Hi,",
        "contractions": True,
        "formality": "medium",
    },
    "enterprise": {
        "max_sentence_length": 35,
        "salutation": "Dear Hiring Team,",
        "contractions": False,
        "formality": "medium",
    },
    "default": {
        "max_sentence_length": 30,
        "salutation": "Hello,",
        "contractions": True,
        "formality": "medium",
    },
}

# Structural rules constants
MAX_CONSECUTIVE_I_STARTS = 2
MAX_SENTENCES_PER_PARAGRAPH = 4
BULLET_ACTION_VERBS = [
    "built", "designed", "implemented", "developed", "led", "managed",
    "created", "launched", "architected", "deployed", "optimized",
    "automated", "integrated", "migrated", "scaled", "reduced",
    "increased", "delivered", "shipped", "established", "owned",
]
