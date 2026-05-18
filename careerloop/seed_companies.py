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
    dict(id="infosys",             name="Infosys",                 domain="infosys.com",       city="Chennai",   sector="Technology & Software", employee_estimate=300000, career_page_url="https://careers.infosys.com"),
    dict(id="wipro",               name="Wipro",                   domain="wipro.com",         city="Chennai",   sector="Technology & Software", employee_estimate=250000, career_page_url="https://careers.wipro.com"),
    dict(id="hcl-technologies",    name="HCL Technologies",        domain="hcltech.com",       city="Chennai",   sector="Technology & Software", employee_estimate=220000, career_page_url="https://www.hcltech.com/careers"),
    dict(id="tech-mahindra",       name="Tech Mahindra",           domain="techmahindra.com",  city="Chennai",   sector="Technology & Software", employee_estimate=150000, career_page_url="https://careers.techmahindra.com"),
    dict(id="lti-mindtree",        name="LTI Mindtree",            domain="ltimindtree.com",   city="Chennai",   sector="Technology & Software", employee_estimate=80000,  career_page_url="https://www.ltimindtree.com/careers/"),
    dict(id="mphasis",             name="Mphasis",                 domain="mphasis.com",       city="Chennai",   sector="Technology & Software", employee_estimate=30000,  career_page_url="https://careers.mphasis.com"),
    dict(id="birlasoft",           name="Birlasoft",               domain="birlasoft.com",     city="Chennai",   sector="Technology & Software", employee_estimate=12000,  career_page_url="https://www.birlasoft.com/careers"),
    dict(id="cyient",              name="Cyient",                  domain="cyient.com",        city="Chennai",   sector="Technology & Software", employee_estimate=15000,  career_page_url="https://www.cyient.com/careers"),
    dict(id="fiserv-india",        name="Fiserv India",            domain="fiserv.com",        city="Chennai",   sector="Finance & Fintech",     employee_estimate=5000,   career_page_url="https://www.fiserv.com/en/about-fiserv/careers.html"),
    dict(id="worldline-india",     name="Worldline India",         domain="worldline.com",     city="Chennai",   sector="Finance & Fintech",     employee_estimate=3000,   career_page_url="https://careers.worldline.com"),
    dict(id="fss-technologies",    name="FSS Technologies",        domain="fsstech.com",       city="Chennai",   sector="Finance & Fintech",     employee_estimate=2000,   career_page_url="https://www.fsstech.com/careers"),
    dict(id="bankbazaar",          name="BankBazaar",              domain="bankbazaar.com",    city="Chennai",   sector="Finance & Fintech",     employee_estimate=500,    career_page_url="https://www.bankbazaar.com/careers.html"),
    dict(id="m2p-fintech",         name="M2P Fintech",             domain="m2pfintech.com",    city="Chennai",   sector="Finance & Fintech",     employee_estimate=800,    career_page_url="https://m2pfintech.com/careers/"),
    dict(id="kissflow",            name="Kissflow",                domain="kissflow.com",      city="Chennai",   sector="Technology & Software", employee_estimate=500,    career_page_url="https://kissflow.com/careers/"),
    dict(id="facilio",             name="Facilio",                 domain="facilio.com",       city="Chennai",   sector="Technology & Software", employee_estimate=300,    career_page_url="https://facilio.com/careers/"),
    dict(id="mad-street-den",      name="Mad Street Den",          domain="madstreetden.com",  city="Chennai",   sector="Technology & Software", employee_estimate=300,    career_page_url="https://www.madstreetden.com/careers"),
    dict(id="pickyourtrail",       name="Pickyourtrail",           domain="pickyourtrail.com", city="Chennai",   sector="Technology & Software", employee_estimate=300,    career_page_url="https://www.pickyourtrail.com/careers"),
    dict(id="kovai-co",            name="Kovai.co",                domain="kovai.co",          city="Chennai",   sector="Technology & Software", employee_estimate=400,    career_page_url="https://www.kovai.co/careers/"),
    dict(id="zarget",              name="Zarget",                  domain="zarget.com",        city="Chennai",   sector="Technology & Software", employee_estimate=100,    career_page_url="https://careers.freshworks.com"),
    dict(id="gofrugal",            name="GoFrugal",                domain="gofrugal.com",      city="Chennai",   sector="Technology & Software", employee_estimate=500,    career_page_url="https://www.gofrugal.com/careers"),
    dict(id="saama-technologies",  name="Saama Technologies",      domain="saama.com",         city="Chennai",   sector="Technology & Software", employee_estimate=2000,   career_page_url="https://www.saama.com/careers/"),
    dict(id="latentview-analytics", name="LatentView Analytics",   domain="latentview.com",    city="Chennai",   sector="Technology & Software", employee_estimate=1000,   career_page_url="https://www.latentview.com/careers/"),
    dict(id="tiger-analytics",     name="Tiger Analytics",         domain="tigeranalytics.com", city="Chennai",  sector="Technology & Software", employee_estimate=3000,   career_page_url="https://www.tigeranalytics.com/careers/"),
    dict(id="fractal-analytics",   name="Fractal Analytics",       domain="fractal.ai",        city="Chennai",   sector="Technology & Software", employee_estimate=4000,   career_page_url="https://fractal.ai/careers/"),
    dict(id="visteon",             name="Visteon",                 domain="visteon.com",       city="Chennai",   sector="Automotive & EV",       employee_estimate=2000,   career_page_url="https://www.visteon.com/careers/"),
    dict(id="danfoss",             name="Danfoss",                 domain="danfoss.com",       city="Chennai",   sector="Technology & Software", employee_estimate=1000,   career_page_url="https://www.danfoss.com/en/about-danfoss/careers/"),
    dict(id="flsmidth",            name="FLSmidth",                domain="flsmidth.com",      city="Chennai",   sector="Technology & Software", employee_estimate=800,    career_page_url="https://www.flsmidth.com/en/careers"),
    dict(id="royal-enfield",       name="Royal Enfield",           domain="royalenfield.com",  city="Chennai",   sector="Automotive & EV",       employee_estimate=8000,   career_page_url="https://www.royalenfield.com/careers"),
    dict(id="ashok-leyland",       name="Ashok Leyland",           domain="ashokleyland.com",  city="Chennai",   sector="Automotive & EV",       employee_estimate=12000,  career_page_url="https://www.ashokleyland.com/careers"),
    dict(id="hyundai-india",       name="Hyundai India",           domain="hyundai.com",       city="Chennai",   sector="Automotive & EV",       employee_estimate=15000,  career_page_url="https://www.hyundai.com/in/en/about-us/careers"),
    dict(id="renault-nissan",      name="Renault Nissan",          domain="renaultnissan.in",  city="Chennai",   sector="Automotive & EV",       employee_estimate=8000,   career_page_url="https://www.renaultnissan.in/careers.html"),
    dict(id="apollo-247",          name="Apollo 24/7",             domain="apollo247.com",     city="Chennai",   sector="Healthcare & Healthtech", employee_estimate=1000,  career_page_url="https://www.apollo247.com/careers"),
    dict(id="kauvery-hospital",    name="Kauvery Hospital",        domain="kauveryhospital.com", city="Chennai", sector="Healthcare & Healthtech", employee_estimate=500,  career_page_url="https://www.kauveryhospital.com/careers"),
    dict(id="medpiper",            name="MedPiper",                domain="medpiper.com",      city="Chennai",   sector="Healthcare & Healthtech", employee_estimate=100,   career_page_url="https://www.medpiper.com/careers"),
    dict(id="specsmakers",         name="Specsmakers",             domain="specsmakers.com",   city="Chennai",   sector="Retail & Commerce",     employee_estimate=800,    career_page_url="https://www.specsmakers.com/careers"),
    dict(id="fashionzone",         name="Fashionzone",             domain="fashionzone.in",    city="Chennai",   sector="Retail & Commerce",     employee_estimate=500,    career_page_url="https://www.fashionzone.in/careers"),
    dict(id="ramco-systems",       name="Ramco Systems",           domain="ramco.com",         city="Chennai",   sector="Technology & Software", employee_estimate=2000,   career_page_url="https://www.ramco.com/careers/"),
    dict(id="temenos-india",       name="Temenos India",           domain="temenos.com",       city="Chennai",   sector="Finance & Fintech",     employee_estimate=1500,   career_page_url="https://www.temenos.com/careers/"),
    dict(id="valeo-india",         name="Valeo India",             domain="valeo.com",         city="Chennai",   sector="Automotive & EV",       employee_estimate=5000,   career_page_url="https://www.valeo.com/en/careers/"),

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
    dict(id="practo",              name="Practo",                  domain="practo.com",        city="Bangalore", sector="Healthcare & Healthtech", employee_estimate=2000,   career_page_url="https://practo.com/careers/"),
    dict(id="medibuddy",           name="MediBuddy",               domain="medibuddy.in",      city="Bangalore", sector="Healthcare & Healthtech", employee_estimate=1000,   career_page_url="https://www.medibuddy.in/careers/"),
    dict(id="pharmeasy",           name="PharmEasy",               domain="pharmeasy.in",      city="Bangalore", sector="Healthcare & Healthtech", employee_estimate=3000,   career_page_url="https://pharmeasy.in/careers/"),
    dict(id="cure-fit",            name="Cure.fit",                domain="cure.fit",          city="Bangalore", sector="Healthcare & Healthtech", employee_estimate=2000,   career_page_url="https://www.cure.fit/careers"),
    dict(id="docsapp",             name="DocsApp",                 domain="docsapp.in",        city="Bangalore", sector="Healthcare & Healthtech", employee_estimate=500,    career_page_url="https://www.docsapp.in/careers"),
    dict(id="mfine",               name="MFine",                   domain="mfine.co",          city="Bangalore", sector="Healthcare & Healthtech", employee_estimate=200,    career_page_url="https://www.mfine.co/careers"),
    dict(id="healthifyme",         name="HealthifyMe",             domain="healthifyme.com",   city="Bangalore", sector="Healthcare & Healthtech", employee_estimate=500,    career_page_url="https://www.healthifyme.com/careers/"),
    dict(id="byjus",               name="BYJU's",                  domain="byjus.com",         city="Bangalore", sector="Education & Edtech",      employee_estimate=15000,  career_page_url="https://byjus.com/careers/"),
    dict(id="unacademy",           name="Unacademy",               domain="unacademy.com",     city="Bangalore", sector="Education & Edtech",      employee_estimate=3000,   career_page_url="https://unacademy.com/careers"),
    dict(id="upgrad",              name="upGrad",                  domain="upgrad.com",        city="Bangalore", sector="Education & Edtech",      employee_estimate=3000,   career_page_url="https://www.upgrad.com/careers/"),
    dict(id="vedantu",             name="Vedantu",                 domain="vedantu.com",       city="Bangalore", sector="Education & Edtech",      employee_estimate=2000,   career_page_url="https://www.vedantu.com/careers"),
    dict(id="simplilearn",         name="Simplilearn",             domain="simplilearn.com",   city="Bangalore", sector="Education & Edtech",      employee_estimate=2000,   career_page_url="https://www.simplilearn.com/careers"),
    dict(id="eruditus",            name="Eruditus",                domain="eruditus.com",      city="Bangalore", sector="Education & Edtech",      employee_estimate=1500,   career_page_url="https://www.eruditus.com/careers/"),
    dict(id="scaler",              name="Scaler",                  domain="scaler.com",        city="Bangalore", sector="Education & Edtech",      employee_estimate=1000,   career_page_url="https://www.scaler.com/careers/"),
    dict(id="druva",               name="Druva",                   domain="druva.com",         city="Bangalore", sector="Technology & Software",   employee_estimate=1500,   career_page_url="https://www.druva.com/careers/"),
    dict(id="icertis",             name="Icertis",                 domain="icertis.com",       city="Bangalore", sector="Technology & Software",   employee_estimate=2000,   career_page_url="https://www.icertis.com/careers/"),
    dict(id="mindtickle",          name="Mindtickle",              domain="mindtickle.com",    city="Bangalore", sector="Technology & Software",   employee_estimate=800,    career_page_url="https://www.mindtickle.com/careers/"),
    dict(id="moengage",            name="MoEngage",                domain="moengage.com",      city="Bangalore", sector="Technology & Software",   employee_estimate=600,    career_page_url="https://www.moengage.com/careers/"),
    dict(id="clevertap",           name="CleverTap",               domain="clevertap.com",     city="Bangalore", sector="Technology & Software",   employee_estimate=1000,   career_page_url="https://clevertap.com/careers/"),
    dict(id="whatfix",             name="Whatfix",                 domain="whatfix.com",       city="Bangalore", sector="Technology & Software",   employee_estimate=800,    career_page_url="https://whatfix.com/careers/"),
    dict(id="capillary-technologies", name="Capillary Technologies", domain="capillarytech.com", city="Bangalore", sector="Technology & Software", employee_estimate=1000,  career_page_url="https://www.capillarytech.com/careers/"),
    dict(id="exotel",              name="Exotel",                  domain="exotel.com",        city="Bangalore", sector="Technology & Software",   employee_estimate=500,    career_page_url="https://exotel.com/careers/"),
    dict(id="kaleyra",             name="Kaleyra",                 domain="kaleyra.com",       city="Bangalore", sector="Technology & Software",   employee_estimate=300,    career_page_url="https://www.kaleyra.com/careers"),
    dict(id="zluri",               name="Zluri",                   domain="zluri.com",         city="Bangalore", sector="Technology & Software",   employee_estimate=300,    career_page_url="https://www.zluri.com/careers/"),
    dict(id="rocketlane",          name="Rocketlane",              domain="rocketlane.com",    city="Bangalore", sector="Technology & Software",   employee_estimate=200,    career_page_url="https://rocketlane.com/careers/"),
    dict(id="highradius",          name="HighRadius",              domain="highradius.com",    city="Bangalore", sector="Technology & Software",   employee_estimate=2000,   career_page_url="https://www.highradius.com/careers/"),
    dict(id="zerodha",             name="Zerodha",                 domain="zerodha.com",       city="Bangalore", sector="Finance & Fintech",       employee_estimate=3000,   career_page_url="https://zerodha.com/careers/"),
    dict(id="upstox",              name="Upstox",                  domain="upstox.com",        city="Bangalore", sector="Finance & Fintech",       employee_estimate=1000,   career_page_url="https://upstox.com/careers/"),
    dict(id="coindcx",             name="CoinDCX",                 domain="coindcx.com",       city="Bangalore", sector="Finance & Fintech",       employee_estimate=500,    career_page_url="https://coindcx.com/careers"),
    dict(id="coinswitch-kuber",    name="CoinSwitch Kuber",        domain="coinswitch.co",     city="Bangalore", sector="Finance & Fintech",       employee_estimate=500,    career_page_url="https://coinswitch.co/careers/"),
    dict(id="bharatpe",            name="BharatPe",                domain="bharatpe.com",      city="Bangalore", sector="Finance & Fintech",       employee_estimate=2000,   career_page_url="https://bharatpe.com/careers/"),
    dict(id="slice",               name="slice",                   domain="sliceit.com",       city="Bangalore", sector="Finance & Fintech",       employee_estimate=500,    career_page_url="https://www.sliceit.com/careers"),
    dict(id="smallcase",           name="smallcase",               domain="smallcase.com",     city="Bangalore", sector="Finance & Fintech",       employee_estimate=300,    career_page_url="https://smallcase.com/careers/"),
    dict(id="open-bank",           name="Open",                    domain="open.money",        city="Bangalore", sector="Finance & Fintech",       employee_estimate=500,    career_page_url="https://open.money/careers/"),
    dict(id="fi-money",            name="Fi Money",                domain="fi.money",          city="Bangalore", sector="Finance & Fintech",       employee_estimate=400,    career_page_url="https://fi.money/careers"),
    dict(id="navi",                name="Navi",                    domain="navi.com",          city="Bangalore", sector="Finance & Fintech",       employee_estimate=1500,   career_page_url="https://www.navi.com/careers"),
    dict(id="dream11",             name="Dream11",                 domain="dream11.com",       city="Bangalore", sector="Gaming & Media",           employee_estimate=1000,   career_page_url="https://www.dream11.com/careers"),
    dict(id="mpl",                 name="MPL",                     domain="mpl.live",          city="Bangalore", sector="Gaming & Media",           employee_estimate=1000,   career_page_url="https://www.mpl.live/careers"),
    dict(id="games24x7",           name="Games24x7",               domain="games24x7.com",     city="Bangalore", sector="Gaming & Media",           employee_estimate=1000,   career_page_url="https://www.games24x7.com/careers/"),
    dict(id="nazara-technologies", name="Nazara Technologies",     domain="nazara.com",        city="Bangalore", sector="Gaming & Media",           employee_estimate=500,    career_page_url="https://www.nazara.com/careers/"),
    dict(id="pocket-fm",           name="Pocket FM",               domain="pocketfm.com",      city="Bangalore", sector="Gaming & Media",           employee_estimate=500,    career_page_url="https://www.pocketfm.com/careers/"),
    dict(id="dailyhunt",           name="Dailyhunt",               domain="dailyhunt.in",      city="Bangalore", sector="Gaming & Media",           employee_estimate=2000,   career_page_url="https://www.dailyhunt.in/careers"),
    dict(id="sharechat",           name="ShareChat",               domain="sharechat.com",     city="Bangalore", sector="Gaming & Media",           employee_estimate=2000,   career_page_url="https://sharechat.com/careers/"),
    dict(id="josh-verse",          name="Josh",                    domain="joshapp.com",       city="Bangalore", sector="Gaming & Media",           employee_estimate=500,    career_page_url="https://joshapp.com/careers/"),
    dict(id="myntra",              name="Myntra",                  domain="myntra.com",        city="Bangalore", sector="Retail & Commerce",       employee_estimate=5000,   career_page_url="https://careers.myntra.com"),
    dict(id="bigbasket",           name="BigBasket",               domain="bigbasket.com",     city="Bangalore", sector="Retail & Commerce",       employee_estimate=8000,   career_page_url="https://www.bigbasket.com/careers/"),
    dict(id="licious",             name="Licious",                 domain="licious.com",       city="Bangalore", sector="Retail & Commerce",       employee_estimate=3000,   career_page_url="https://www.licious.com/careers/"),
    dict(id="dunzo",               name="Dunzo",                   domain="dunzo.com",         city="Bangalore", sector="Retail & Commerce",       employee_estimate=1000,   career_page_url="https://www.dunzo.com/careers"),
    dict(id="blinkit",             name="Blinkit",                 domain="blinkit.com",       city="Bangalore", sector="Retail & Commerce",       employee_estimate=3000,   career_page_url="https://blinkit.com/careers"),
    dict(id="sap-labs-india",      name="SAP Labs India",          domain="sap.com",           city="Bangalore", sector="Technology & Software",   employee_estimate=15000,  career_page_url="https://www.sap.com/india/about/careers.html"),
    dict(id="oracle-india",        name="Oracle India",            domain="oracle.com",        city="Bangalore", sector="Technology & Software",   employee_estimate=40000,  career_page_url="https://www.oracle.com/in/careers/"),
    dict(id="vmware-india",        name="VMware India",            domain="vmware.com",        city="Bangalore", sector="Technology & Software",   employee_estimate=8000,   career_page_url="https://careers.vmware.com"),
    dict(id="dell-india",          name="Dell Technologies",       domain="dell.com",          city="Bangalore", sector="Technology & Software",   employee_estimate=25000,  career_page_url="https://jobs.dell.com"),
    dict(id="cisco-india",         name="Cisco India",             domain="cisco.com",         city="Bangalore", sector="Technology & Software",   employee_estimate=15000,  career_page_url="https://www.cisco.com/c/en/us/about/careers.html"),
    dict(id="intel-india",         name="Intel India",             domain="intel.com",         city="Bangalore", sector="Technology & Software",   employee_estimate=15000,  career_page_url="https://www.intel.com/content/www/us/en/jobs/locations/india.html"),
    dict(id="adobe-india",         name="Adobe India",             domain="adobe.com",         city="Bangalore", sector="Technology & Software",   employee_estimate=7000,   career_page_url="https://www.adobe.com/careers.html"),
    dict(id="uber-india",          name="Uber India",              domain="uber.com",          city="Bangalore", sector="Technology & Software",   employee_estimate=3000,   career_page_url="https://www.uber.com/us/en/careers/"),
    dict(id="porter",              name="Porter",                  domain="theporter.in",      city="Bangalore", sector="Logistics & Supply Chain", employee_estimate=1000,   career_page_url="https://porter.in/careers/"),
    dict(id="blackbuck",           name="BlackBuck",               domain="blackbuck.com",     city="Bangalore", sector="Logistics & Supply Chain", employee_estimate=1500,   career_page_url="https://www.blackbuck.com/careers/"),
    dict(id="delhivery",           name="Delhivery",               domain="delhivery.com",     city="Bangalore", sector="Logistics & Supply Chain", employee_estimate=5000,   career_page_url="https://www.delhivery.com/careers/"),
    dict(id="shiprocket",          name="Shiprocket",              domain="shiprocket.in",     city="Bangalore", sector="Logistics & Supply Chain", employee_estimate=1000,   career_page_url="https://www.shiprocket.in/careers/"),
    dict(id="haptik",              name="Haptik",                  domain="haptik.ai",         city="Bangalore", sector="Technology & Software",   employee_estimate=500,    career_page_url="https://www.haptik.ai/careers"),
    dict(id="observe-ai",          name="Observe.AI",              domain="observe.ai",        city="Bangalore", sector="Technology & Software",   employee_estimate=800,    career_page_url="https://www.observe.ai/careers"),
    dict(id="yellow-ai",           name="Yellow.ai",               domain="yellow.ai",         city="Bangalore", sector="Technology & Software",   employee_estimate=700,    career_page_url="https://yellow.ai/careers/"),
    dict(id="gupshup",             name="Gupshup",                 domain="gupshup.io",        city="Bangalore", sector="Technology & Software",   employee_estimate=1000,   career_page_url="https://www.gupshup.io/careers/"),
    dict(id="nobroker",            name="NoBroker",                domain="nobroker.in",       city="Bangalore", sector="Technology & Software",   employee_estimate=2000,   career_page_url="https://www.nobroker.in/careers"),
    dict(id="quikr",               name="Quikr",                   domain="quikr.com",         city="Bangalore", sector="Retail & Commerce",       employee_estimate=1500,   career_page_url="https://www.quikr.com/careers"),
    dict(id="udaan",               name="Udaan",                   domain="udaan.com",         city="Bangalore", sector="Retail & Commerce",       employee_estimate=3000,   career_page_url="https://www.udaan.com/careers/"),
    dict(id="urban-company",       name="Urban Company",           domain="urbancompany.com",  city="Bangalore", sector="Technology & Software",   employee_estimate=3000,   career_page_url="https://www.urbancompany.com/careers"),
    dict(id="inmobi",              name="InMobi",                  domain="inmobi.com",        city="Bangalore", sector="Gaming & Media",           employee_estimate=2000,   career_page_url="https://www.inmobi.com/careers/"),
    dict(id="zeta",                name="Zeta",                    domain="zeta.tech",         city="Bangalore", sector="Finance & Fintech",       employee_estimate=1000,   career_page_url="https://www.zeta.tech/careers/"),
    dict(id="khatabook",           name="Khatabook",               domain="khatabook.com",     city="Bangalore", sector="Finance & Fintech",       employee_estimate=500,    career_page_url="https://khatabook.com/careers/"),
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
