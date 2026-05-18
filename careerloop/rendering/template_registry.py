import os

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

TEMPLATE_REGISTRY = {
    "classic-ats": {
        "file": "classic_ats.html",
        "description": "Single column, black/white, maximum ATS compatibility.",
        "one_page_mode": False
    },
    "modern-accent": {
        "file": "modern_accent.html",
        "description": "Single column with subtle accent color.",
        "one_page_mode": False
    },
    "executive-clean": {
        "file": "executive_clean.html",
        "description": "Elegant layout, stronger whitespace.",
        "one_page_mode": False
    },
    "compact-one-page": {
        "file": "compact_one_page.html",
        "description": "Aggressive density optimization.",
        "one_page_mode": True
    },
    "technical-two-column": {
        "file": "technical_two_column.html",
        "description": "Left sidebar for contact/skills/education.",
        "one_page_mode": False
    },
    "product-engineer": {
        "file": "product_engineer.html",
        "description": "Modern product layout, strong callouts.",
        "one_page_mode": False
    },
    "founder-operator": {
        "file": "founder_operator.html",
        "description": "Highlights founder metrics and ownership.",
        "one_page_mode": False
    }
}
