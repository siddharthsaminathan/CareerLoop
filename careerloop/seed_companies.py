"""
Seed known Indian tech companies into registry.

ONLY seeds identity data: name, domain, career_page_url, city, sector, headcount.
NO ats_provider. NO ats_url. NO guessing.

ATS detection is a separate step: python3 -m careerloop.detect_ats_pass
That pass probes career pages → fills ats_provider + ats_url in DB.
"""

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from careerloop.company_registry import CompanyRecord, CompanyRegistry

# fmt: off
SEED_COMPANIES = [
    # ── Chennai ──────────────────────────────────────────────────────
    dict(id="freshworks",          name="Freshworks",              domain="freshworks.com",    city="Chennai",   sector="Technology & Software", employee_estimate=5000,   career_page_url="https://careers.freshworks.com"),
    dict(id="zoho",                name="Zoho",                    domain="zoho.com",          city="Chennai",   sector="Technology & Software", employee_estimate=15000,  career_page_url="https://careers.zoho.com"),
    dict(id="chargebee",           name="Chargebee",               domain="chargebee.com",     city="Chennai",   sector="Finance & Fintech",     employee_estimate=1000,   career_page_url="https://www.chargebee.com/careers/"),
    dict(id="setu",                name="Setu",                    domain="setu.co",           city="Chennai",   sector="Finance & Fintech",     employee_estimate=200,    career_page_url="https://setu.co/careers"),
    dict(id="perfios",             name="Perfios",                 domain="perfios.com",       city="Chennai",   sector="Finance & Fintech",     employee_estimate=1500,   career_page_url="https://www.perfios.com/careers"),
    dict(id="detect-technologies", name="Detect Technologies",     domain="detect.com",        city="Chennai",   sector="Technology & Software", employee_estimate=200,    career_page_url="https://www.detect.com/careers"),
    dict(id="uniphore",            name="Uniphore",                domain="uniphore.com",      city="Chennai",   sector="Technology & Software", employee_estimate=700,    career_page_url="https://www.uniphore.com/careers/"),
    dict(id="tcs",                 name="TCS",                     domain="tcs.com",           city="Chennai",   sector="Technology & Software", employee_estimate=600000, career_page_url="https://www.tcs.com/careers"),
    dict(id="cognizant",           name="Cognizant",               domain="cognizant.com",     city="Chennai",   sector="Technology & Software", employee_estimate=300000, career_page_url="https://careers.cognizant.com"),
    dict(id="hexaware",            name="Hexaware",                domain="hexaware.com",      city="Chennai",   sector="Technology & Software", employee_estimate=30000,  career_page_url="https://hexaware.com/careers/"),
    dict(id="payu-india",          name="PayU India",              domain="payu.in",           city="Chennai",   sector="Finance & Fintech",     employee_estimate=2000,   career_page_url="https://payu.in/careers"),
    dict(id="ola-electric",        name="Ola Electric",            domain="olaelectric.com",   city="Chennai",   sector="Technology & Software", employee_estimate=3000,   career_page_url="https://olaelectric.com/careers"),
    dict(id="accenture",           name="Accenture India",         domain="accenture.in",      city="Chennai",   sector="Technology & Software", employee_estimate=300000, career_page_url="https://www.accenture.com/in-en/careers"),
    dict(id="grant-thornton",      name="Grant Thornton India",    domain="grantthornton.in",  city="Chennai",   sector="Finance & Fintech",     employee_estimate=8000,   career_page_url="https://grantthornton.in/careers/"),
    dict(id="redbus",              name="redBus",                  domain="redbus.in",         city="Chennai",   sector="Technology & Software", employee_estimate=800,    career_page_url="https://careers.redbus.in"),

    # ── Bangalore ────────────────────────────────────────────────────
    dict(id="flipkart",            name="Flipkart",                domain="flipkart.com",      city="Bangalore", sector="Retail & Commerce",     employee_estimate=50000,  career_page_url="https://www.flipkart.com/careers"),
    dict(id="meesho",              name="Meesho",                  domain="meesho.com",        city="Bangalore", sector="Retail & Commerce",     employee_estimate=3000,   career_page_url="https://meesho.io/careers"),
    dict(id="swiggy",              name="Swiggy",                  domain="swiggy.com",        city="Bangalore", sector="Technology & Software", employee_estimate=5000,   career_page_url="https://careers.swiggy.com"),
    dict(id="razorpay",            name="Razorpay",                domain="razorpay.com",      city="Bangalore", sector="Finance & Fintech",     employee_estimate=3000,   career_page_url="https://razorpay.com/jobs/"),
    dict(id="cred",                name="CRED",                    domain="cred.club",         city="Bangalore", sector="Finance & Fintech",     employee_estimate=1500,   career_page_url="https://careers.cred.club"),
    dict(id="zepto",               name="Zepto",                   domain="zeptonow.com",      city="Bangalore", sector="Retail & Commerce",     employee_estimate=2000,   career_page_url="https://www.zeptonow.com/careers"),
    dict(id="sarvam-ai",           name="Sarvam AI",               domain="sarvam.ai",         city="Bangalore", sector="Technology & Software", employee_estimate=100,    career_page_url="https://www.sarvam.ai/about"),
    dict(id="krutrim",             name="Krutrim",                 domain="krutrim.ai",        city="Bangalore", sector="Technology & Software", employee_estimate=300,    career_page_url="https://krutrim.ai/careers"),
    dict(id="ola-cabs",            name="Ola Cabs",                domain="olacabs.com",       city="Bangalore", sector="Technology & Software", employee_estimate=5000,   career_page_url="https://www.olacabs.com/careers"),
    dict(id="phonepe",             name="PhonePe",                 domain="phonepe.com",       city="Bangalore", sector="Finance & Fintech",     employee_estimate=4000,   career_page_url="https://www.phonepe.com/careers/"),
    dict(id="paytm",               name="Paytm",                   domain="paytm.com",         city="Bangalore", sector="Finance & Fintech",     employee_estimate=8000,   career_page_url="https://paytm.com/about-us/careers/"),
    dict(id="groww",               name="Groww",                   domain="groww.in",          city="Bangalore", sector="Finance & Fintech",     employee_estimate=2000,   career_page_url="https://groww.in/company/careers"),
    dict(id="browserstack",        name="BrowserStack",            domain="browserstack.com",  city="Bangalore", sector="Technology & Software", employee_estimate=2000,   career_page_url="https://www.browserstack.com/careers"),
    dict(id="hasura",              name="Hasura",                  domain="hasura.io",         city="Bangalore", sector="Technology & Software", employee_estimate=200,    career_page_url="https://hasura.io/careers/"),
    dict(id="postman",             name="Postman",                 domain="postman.com",       city="Bangalore", sector="Technology & Software", employee_estimate=800,    career_page_url="https://www.postman.com/careers/"),
    dict(id="simpl",               name="Simpl",                   domain="getsimpl.com",      city="Bangalore", sector="Finance & Fintech",     employee_estimate=500,    career_page_url="https://getsimpl.com/careers"),
    dict(id="jupiter-money",       name="Jupiter Money",           domain="jupiter.money",     city="Bangalore", sector="Finance & Fintech",     employee_estimate=400,    career_page_url="https://jupiter.money/careers"),
    dict(id="darwinbox",           name="Darwinbox",               domain="darwinbox.com",     city="Bangalore", sector="Technology & Software", employee_estimate=1000,   career_page_url="https://darwinbox.com/about/careers"),
    dict(id="ninjacart",           name="Ninjacart",               domain="ninjacart.com",     city="Bangalore", sector="Retail & Commerce",     employee_estimate=1500,   career_page_url="https://www.ninjacart.com/careers/"),
    dict(id="leadsquared",         name="LeadSquared",             domain="leadsquared.com",   city="Bangalore", sector="Technology & Software", employee_estimate=1200,   career_page_url="https://www.leadsquared.com/careers/"),
    dict(id="amazon-india",        name="Amazon India",            domain="amazon.in",         city="Bangalore", sector="Retail & Commerce",     employee_estimate=100000, career_page_url="https://www.amazon.jobs/en/locations/bangalore-india"),
    dict(id="google-india",        name="Google India",            domain="google.co.in",      city="Bangalore", sector="Technology & Software", employee_estimate=10000,  career_page_url="https://careers.google.com/locations/bangalore/"),
    dict(id="microsoft-india",     name="Microsoft India",         domain="microsoft.com",     city="Bangalore", sector="Technology & Software", employee_estimate=20000,  career_page_url="https://careers.microsoft.com/v2/global/en/india.html"),
    dict(id="walmart-global-tech", name="Walmart Global Tech",     domain="walmart.com",       city="Bangalore", sector="Retail & Commerce",     employee_estimate=50000,  career_page_url="https://careers.walmart.com/results?q=product+manager&location=Bengaluru"),
    dict(id="airtel",              name="Airtel",                  domain="airtel.in",         city="Bangalore", sector="Technology & Software", employee_estimate=20000,  career_page_url="https://www.airtel.in/careers"),
    dict(id="juspay",              name="Juspay",                  domain="juspay.in",         city="Bangalore", sector="Finance & Fintech",     employee_estimate=500,    career_page_url="https://juspay.in/careers"),
    dict(id="contlo",              name="Contlo",                  domain="contlo.com",        city="Bangalore", sector="Technology & Software", employee_estimate=100,    career_page_url="https://contlo.com/careers"),
]
# fmt: on


def seed(root: str = None):
    reg = CompanyRegistry(root)
    count = 0
    for data in SEED_COMPANIES:
        rec = CompanyRecord(
            id=data["id"],
            name=data["name"],
            domain=data["domain"],
            city=data["city"],
            sector=data["sector"],
            employee_estimate=data["employee_estimate"],
            career_page_url=data["career_page_url"],
            ats_provider="unknown",   # detect_ats_pass fills this
            ats_url="",               # detect_ats_pass fills this
            crawl_status="pending",
        )
        reg.upsert(rec)
        count += 1
    print(f"Seeded {count} companies (ATS detection pending).")
    return count


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else ROOT
    seed(root)
