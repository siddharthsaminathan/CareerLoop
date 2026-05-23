Critical instructions for the agent that is building this guy will say: don't build company scrapers and all that. This guy just understands how to build the ATS adapters and then build it. Don't remember whatever this guy is saying about don't build company scraper and all, okay.

  How We Search the Internet — Full Map The actual flow when a user's resume hits the system: Resume → ProfileManager extracts skills, target roles, city → RoleKeywordCache calls DeepSeek to generate keywords → OnDemandSearch.run() starts: Phase A — Employer Discovery What it does: Finds companies in Bangalore that likely hire for your role. No job listings yet — just company names. 5 sources, all via DuckDuckGo (ddgs library): Source DDG Query Pattern Example GoogleMapsDiscovery "AI" technology companies Bangalore India finds sarvam.ai, krutrim.ai WellfoundDiscovery site:wellfound.com "AI/ML" startup Bangalore finds wellfound.com/company/... pages CrunchbaseDiscovery site:crunchbase.com "AI" startup Bangalore finds crunchbase.com/organization/... Inc42Discovery site:inc42.com AI startup Bangalore finds inc42.com/startups/... YCDiscovery site:ycombinator.com/companies Bangalore AI finds YC-batch companies Results stored in SQLite companies table. Scored by CompanyTargeting (sector match + crawl freshness + function probability). Returns all companies with score > 50. Gap: Wellfound/Crunchbase/LinkedIn do NOT expose APIs — DDG returns their public pages, which have company names but not job counts. Real-time hiring signal is weak. Phase B — Job Board Search 6 sources, running in parallel (ThreadPoolExecutor(6)): Source Mechanism What it hits SearchAdapter Google scrape → DDG fallback google.com/search?q="AI Product Engineer" jobs Bangalore, then duckduckgo if Google 200 fails JobSpyAdapter python-jobspy library Scrapes linkedin.com/jobs + indeed.co.in (returns short snippets, 500 chars max) NaukriAdapter Playwright + XHR intercept Opens naukri.com, intercepts jobapi XHR, extracts JSON response MonsterAdapter DDG site:foundit.in "AI Product Engineer" Bangalore site:foundit.in GlassdoorAdapter DDG site:glassdoor.com "AI Product Engineer" Bangalore site:glassdoor.com/job-listing GoogleJobsAdapter DDG targeting ATS boards "AI Product Engineer" Bangalore site:lever.co OR site:greenhouse.io Phase C — ATS APIs (direct, no scraping) For companies discovered in Phase A that have known ATS: ATS How Direct URL Greenhouse REST JSON boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true Lever REST JSON api.lever.co/v0/postings/{slug}?mode=json Ashby REST JSON api.ashbyhq.com/posting-api/job-board/{slug} Workday Playwright + XHR intercept {slug}.myworkdayjobs.com/wday/cxs/{slug}/{slug}/jobs These are the highest quality results — live, structured, full JD text. Phase D — JD Extraction (for Phase B URLs) Phase B returns mostly URLs, not full job descriptions. Three extraction methods in order: Method How Quality ScrapeGraphAdapter Playwright render → DeepSeek LLM extraction Best — structured output IndeedScraper indeed.com/viewjob?jk={id} JSON API Good for Indeed URLs _extract_generic_jd requests + BeautifulSoup container heuristics Fallback for any URL ScrapeGraph is working. It's NOT the cloud ScrapeGraph API — it's our own scrapegraph_adapter.py that uses Playwright + DeepSeek. Zero ScrapeGraph API key needed. Evidence: run 1 ranks 4, 8, 10, 12, 14 all have _source_type=scrapegraph. Does the system know if a job is open? Source Liveness How Greenhouse/Lever/Ashby ✅ Yes API returns only active postings Workday ✅ Yes XHR intercept of live board Naukri XHR ⚠️ Mostly Naukri marks closed jobs but API doesn't always filter DDG-sourced (JobSpy, Monster, Glassdoor, Google Jobs) ❌ No Search snippets only — no liveness check Gap: ~60% of Phase B results (DDG + JobSpy) have no liveness signal. The LLM validator (FIX 20, just implemented) filters bad content but can't confirm a posting is still open. Linkup / WebBridge Assessment Linkup (linkup.so) — paid search API, structured job data, real-time index. Useful if DDG results become unreliable or rate-limited. Not needed right now — DDG is working. WebBridge (Kimi) — cloud browser execution, solves anti-bot. Useful if local Playwright starts failing on Naukri or Workday. Not needed right now — Playwright with --no-sandbox is working. Verdict: Both are backup options. Current infra is functional. Evaluate Linkup if DDG gets rate-limited at scale. Current Gaps Summary Gap Impact Fix needed DDG-sourced jobs have no liveness check Stale postings in results Per-URL status probe (check for "no longer accepting") JobSpy returns 500-char snippets only Score compression (61-74 band, no spread) Full JD fetch for JobSpy URLs Naukri Playwright requires headful Chrome Flaky in CI/headless WebBridge as fallback Wellfound shows company pages, not job listings Phase A only, no direct job links Wellfound auth token or SpireAI intercept LinkedIn blocked JobSpy rate-limited Accept limitation, focus on Naukri/ATS ----- do a deep https://gtprod.talentrecruit.com/career-page search on whatever ATS systems are available, Machan. Let's fucking do that. Also, bolai, search whatever ATS systems are available in the entire world and rank them, bro. We need to find that 20% of the ATS systems that cover 80% of jobs, bro. 80% of the jobs covered is also good. Right now we only have 4 ATS systems, bro. What happened to Talent Recruit, Search Recruit, or whatever the fuck this Career Recruit thing is that I always see, Smart Recruit, and all of that? What I want you to do is do a deep search. I want you to go check the web on what all the ATS systems are available. If you look at careers.grantthornton.com, I will tell you something, Machan. If you look at it, it's like Talent Recruit and all of that, Machan. What I want to do is let's build all the fucking ATS adapters, bro, Machan. We're going to go look at Audi, go look at BMW, go look at some from a random AI company like Omnics Solutions, to fucking high-level, Machan. Go, go fucking read all of that. Find all the ATS things that cover 80% of job applications and even 100% if it works, and then tell me what I'm missing so we can also build the adapter for that, bro


Good. Now THIS is the right direction.
You are finally thinking correctly: NOT scraping random career pages, but:

capture the ATS layer of the internet

That is MUCH smarter.
Because: 20% of ATS systems probably cover: 70–90% of structured hiring globally.
That is the real leverage point.
And yes: you are missing MANY important ATS systems.
Right now your stack is too startup-tech biased:
* Greenhouse
* Lever
* Ashby
* Workday
Good for startups. Terrible for enterprise/global coverage.
THE REAL ATS MAP
There are 4 major categories.

CATEGORY 1 — MODERN STARTUP ATS
Covers:
* startups
* SaaS
* VC-backed
* tech
These are already mostly covered.
ATS	Priority	Status
Greenhouse	P0	Done
Lever	P0	Done
Ashby	P0	Partial
Workable	P1	Missing
Teamtailor	P1	Missing
SmartRecruiters	P0	Missing
Recruitee	P2	Missing
BambooHR Hiring	P2	Missing
These cover: modern startup hiring.

CATEGORY 2 — ENTERPRISE ATS
THIS is your missing world.
Covers:
* MNCs
* consulting firms
* automotive
* manufacturing
* banks
* conglomerates
VERY IMPORTANT.
ATS	Priority	Notes
Workday	P0	Massive coverage
SAP SuccessFactors	P0	HUGE globally
Oracle Taleo	P0	Huge legacy enterprise
iCIMS	P0	Massive US coverage
SmartRecruiters	P0	Growing fast
Avature	P1	Big enterprise
Phenom	P1	Enterprise AI recruiting
PageUp	P2	APAC/enterprise
Cornerstone	P2	Enterprise HR
UKG	P2	Enterprise HR
THIS is where: BMW Audi Grant Thornton large consulting firms banks etc live.

CATEGORY 3 — INDIA-SPECIFIC ATS
You are massively underestimating this category.
ATS	Priority
TalentRecruit	P0
Darwinbox Recruiting	P0
PeopleStrong	P1
Freshteam	P1
Zoho Recruit	P1
Ceipal	P2
TurboHire	P2
THIS is where: Indian enterprises, mid-market, consulting, manufacturing, staffing live.
VERY important.

CATEGORY 4 — CUSTOM CAREER PLATFORMS
Fashion companies. Retail. Commerce. Conglomerates.
Usually:
* custom React
* custom CMS
* embedded APIs
* no public ATS
Examples:
* Nike
* FabIndia
* Shoppers Stop
These require:

browser-native extraction

NOT adapters.

YOUR MOST IMPORTANT NEXT MOVE
You need:

ATS fingerprinting engine

THIS is the missing architecture.
HOW IT WORKS
Given:

career_page_url

Detect:
* greenhouse
* lever
* workday
* successfactors
* taleo
* smartrecruiters
* talentrecruit
* darwinbox etc.
Using:
* script tags
* network requests
* DOM markers
* URLs
* GraphQL endpoints
* JS bundles
Example:

jobs.smartrecruiters.com
wd3.myworkdayjobs.com
career5.successfactors.com
talentrecruit.com
oraclecloud.com

Then: route to correct adapter.
THIS is scalable.
NOT: manual adapters per company.

YOUR MISSING P0 ADAPTERS
Build THESE immediately:
P0
* SmartRecruiters
* SAP SuccessFactors
* Oracle Taleo
* iCIMS
* TalentRecruit
* Darwinbox
These alone probably DOUBLE coverage.
Especially: TalentRecruit + Darwinbox for India.

VERY IMPORTANT
You DO NOT need: 100 ATS adapters.
You need: the dominant 15–20.
That probably gets: 80%+ coverage.
Exactly your intuition.

WHAT YOU SHOULD TELL THE TEAM
STOP
building:

company-specific scrapers

START
building:

ATS fingerprint → adapter router

Architecture:

career_url
    ↓
ATS fingerprint detector
    ↓
adapter router
    ↓
structured extraction

THAT is the correct architecture.

TALENTRECRUIT
Your instinct correct.
TalentRecruit Career Page Example
This is a BIG missing gap.
Grant Thornton India, many Indian enterprises, consulting firms, mid-market firms use this.
This should become: P0 adapter.

YOUR TRUE COVERAGE STRATEGY
Layer 1
ATS adapters (cheap + scalable)
Layer 2
browser-native extraction (for custom portals)
Layer 3
job boards (fallback + breadth)
That is the final architecture.

MOST IMPORTANT INSIGHT
The ATS layer is effectively:

the operating system layer of hiring

If you capture it well, you basically index: the structured labor market.

Machan, so now tell me, how the fuck do we build all of these ATS adapters, bro? We've already built adapters for Greenhouse, Lever, Ashby, and everything. Can you just give me a strategy for: - Workable - Team tailored - Smart recruiters - Recruity - Bamboo HR - Hiring and then the same thing for: - Workday - SAP - Oracle - Teleo - ICMS - Smart recruiters How about you, machan, for everything? Give me a strategy on how to build this shit, bro, so that I can have it as a document and I can make this guy build it, bro. Okay.


UNIVERSAL ATS ADAPTER STRATEGY
Every ATS adapter should follow SAME architecture.

career_url
    ↓
fingerprint detector
    ↓
adapter router
    ↓
job extractor
    ↓
normalized job schema

DO NOT build random scrapers.
ALL adapters should implement:

class ATSAdapter:
    async def detect(self, url, html, network_logs):
        pass

    async def extract_jobs(self, url):
        pass

Return:

{
  "title": "",
  "location": "",
  "description": "",
  "apply_url": "",
  "job_id": "",
  "department": ""
}

Universal schema.

HOW TO BUILD EACH ADAPTER
There are ONLY 4 extraction patterns.
PATTERN 1 — PUBLIC JSON API
BEST.
Example: Greenhouse.
Flow:

detect endpoint
→ call API
→ normalize JSON

Cheap + scalable.

PATTERN 2 — GRAPHQL API
Ashby-style.
Flow:

intercept GraphQL
→ replay query
→ extract JSON


PATTERN 3 — RENDERED DOM
Workable/Teamtailor-style.
Flow:

Playwright render
→ wait network idle
→ extract rendered cards


PATTERN 4 — FULL AGENTIC
Worst case.
Needed for:
* SAP
* Taleo
* custom portals
Flow:

click
scroll
paginate
expand
extract


ADAPTER STRATEGY BY ATS
1. WORKABLE
Workable
Fingerprints
Look for:

jobs.workable.com
workable.com/j/

Extraction
Usually: rendered JSON embedded.
Check:

<script id="__NEXT_DATA__">

OR: XHR calls.
Implementation:

await page.goto(url)
html = await page.content()

Extract:
* job cards
* JSON blobs
Priority: P1.
Easy.

2. TEAMTAILOR
Teamtailor
Fingerprints

teamtailor.com/jobs

Extraction
Usually: clean JSON API.
Intercept:

api/v1/jobs

Implementation: network interception first.
Then: DOM fallback.
Priority: P1.
Easy.

3. SMARTRECRUITERS
SmartRecruiters
VERY IMPORTANT.
Huge coverage.
Fingerprints

jobs.smartrecruiters.com

Extraction
Usually: public JSON endpoints.
Example patterns:

https://api.smartrecruiters.com/v1/companies/{company}/postings

Implementation: detect company slug. Call API directly.
Priority: P0.

4. RECRUITEE
Recruitee
Fingerprints

jobs.recruitee.com

Extraction
Usually: embedded JSON.
Can use:

/api/offers

Implementation: network intercept + DOM.
Priority: P2.

5. BAMBOOHR HIRING
BambooHR
Fingerprints

bamboohr.com/careers

Extraction
Usually: rendered HTML + JSON.
Need: Playwright rendering.
Priority: P2.

6. WORKDAY
Workday
MOST IMPORTANT.
Fingerprints

myworkdayjobs.com
wd1
wd3
wd5

Strategy
DO NOT: guess REST URLs.
Correct:

Playwright
→ intercept XHR
→ capture /jobs API

Workday heavily dynamic.
Need: browser-native extraction.
Priority: P0.

7. SAP SUCCESSFACTORS
SAP SuccessFactors
VERY IMPORTANT.
Huge enterprise coverage.
Fingerprints

career5.successfactors.com
jobs2web

Strategy
Usually: jobs rendered via JSON APIs.
Need: network interception.
Fallback: DOM extraction.
Some require: pagination clicks.
Priority: P0.

8. ORACLE TALEO
Oracle Taleo
Huge legacy coverage.
Banks/enterprise.
Fingerprints

taleo.net
oraclecloud.com

Problem
Terrible HTML. Ancient systems.
Strategy
Mostly: DOM extraction.
Sometimes: XHR hidden.
Need: Playwright + BeautifulSoup.
Priority: P0.
Harder than others.

9. ICIMS
iCIMS
Massive US coverage.
Fingerprints

icims.com/jobs

Strategy
Usually: JSON endpoints exposed.
Network interception first.
Then: DOM fallback.
Priority: P0.

10. TALENTRECRUIT
TalentRecruit
India-specific. IMPORTANT.
Fingerprints

talentrecruit.com
career-page

Strategy
Browser render first.
Likely: XHR job feed.
Need: network intercept.
Priority: P0.

11. DARWINBOX
Darwinbox
India enterprise HR.
Fingerprints

darwinbox

Strategy
Likely: SPA React app.
Need: browser rendering.
Priority: P1.

THE REAL IMPLEMENTATION STRATEGY
STEP 1 — BUILD FINGERPRINT ENGINE
Input:

career_url

Detect:

FINGERPRINTS = {
  "workday": ["myworkdayjobs"],
  "greenhouse": ["greenhouse.io"],
  "smartrecruiters": ["smartrecruiters"],
  "taleo": ["taleo.net"],
}

Check:
* URL
* scripts
* network logs
* DOM markers
Return:

{
  "platform": "workday"
}

THIS is P0.

STEP 2 — ADAPTER ROUTER

adapter = registry[platform]
jobs = await adapter.extract_jobs()


STEP 3 — STANDARDIZED EXTRACTION
Every adapter returns SAME schema.
No exceptions.

STEP 4 — FALLBACK CASCADE
If: API fails:

API
→ XHR intercept
→ rendered DOM
→ agentic browser

Universal fallback architecture.

STEP 5 — TEST SUITE
Every adapter MUST have:

known company
known ATS
expected job count
expected fields

Example:

assert len(jobs) > 0
assert jobs[0]["title"]


PRIORITY ORDER
P0
Build immediately:
* Workday
* SAP SuccessFactors
* SmartRecruiters
* iCIMS
* Taleo
* TalentRecruit
These massively expand coverage.

P1
Then:
* Workable
* Teamtailor
* Darwinbox

P2
Then:
* Recruitee
* BambooHR
* niche ATSs

MOST IMPORTANT
DO NOT build:

company-specific scrapers

Build:

platform adapters

That is the scalable architecture.
