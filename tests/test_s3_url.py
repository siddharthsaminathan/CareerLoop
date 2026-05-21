from careerloop.company_intel import _gather_web_sources

company = "Nicobar Design Pvt. Ltd."
job_url = "https://www.nicobar.com/pages/careers"
print(f"Gathering sources for {company} with URL {job_url}...")
sources = _gather_web_sources(company, job_url)
print(f"Found {len(sources)} sources.")
for s in sources:
    print(f"- {s.get('source_type')}: {s.get('url')}")
