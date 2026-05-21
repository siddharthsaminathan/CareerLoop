import re
def _normalize_company(name: str) -> str:
    """Slugify company name for cache keys and file paths."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")
    return slug or "unknown"

print(_normalize_company("Nicobar Design Pvt. Ltd."))
