import sys
from careerloop.company_intel import _gather_web_sources

company = "Nicobar Design Pvt Ltd"
print(f"Gathering sources for {company}...")
sources = _gather_web_sources(company)
print(f"Found {len(sources)} sources.")
for s in sources:
    print(f"- {s.get('source_type')}: {s.get('url')}")
