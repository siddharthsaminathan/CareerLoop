import os
import sys
import json
from dotenv import load_dotenv

# Load env variables from current directory
ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT, ".env"))

from careerloop.outreach_engine import OutreachEngine

def main():
    print("=" * 60)
    print("🤖 STARTING OUTREACH ENGINE LIVE TEST")
    print("=" * 60)

    # 1. Define job profile & details
    company_name = "BukuWarung"
    role_title = "AI Product Engineer"
    jd_text = """Function: Software Engineering → Other Software Development Generative AI Python DevOps LLMs Machine Learning Java +3 more MLOps MCP Deployment We are looking for a highly skilled AI Productivity Engineer to lead the development and integration of AI-driven solutions, driving automation and efficiency across multiple business functions. In this role, you will play a crucial part in building scalable tools and workflows, optimizing internal processes, and fostering continuous productivity improvements. Your expertise will directly contribute to accelerating our GTM strategy, enhancing operational scalability, and shaping the future of AI adoption within our company. The role, in our view, is split across three core areas of responsibility. The core responsibilities for the job include the following: AI-Powered Automation and Operational Scaling: Lead the development and integration of cost-effective AI systems, leveraging LLMs and AI agents to optimize business operations, automate workflows, and improve customer support processes. Implement AI-based self-serve tools to reduce operational dependencies. Collaborate with product and engineering teams to integrate AI-driven automation into products, customer support, and internal operations. Identify and implement AI tools to enhance team productivity, GTM strategies, and business scalability."""

    user_profile = {
        "full_name": "Siddharth Saminathan",
        "headline": "AI Product Engineer — multi-agent systems, production AI, 0-to-1 builder",
        "narrative": "4+ years shipping production AI: built Emote from zero (450+ users, 13-15% retention), built enterprise agentic quality management at Omnex. I ship fast and optimize relentlessly.",
        "superpowers": [
            "Multi-agent orchestration (LangGraph, tool-driven architectures)",
            "Production AI at scale — latency from 15s→3s, cost $1.20→$0.023",
            "0-to-1 product builder — concept to prod, then iterate on real user data"
        ],
        "proof_points": [
            {"name": "Emote — AI companion app", "metric": "450+ users, 75% activation, 13-15% weekly retention"},
            {"name": "Omnex Agentic Quality System", "metric": "Automates DFMEA/PFMEA/8D for global manufacturing"}
        ]
    }

    # 2. Initialize Engine
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("💥 ERROR: DEEPSEEK_API_KEY is not set in env.")
        sys.exit(1)

    print("\n[Engine Initialization] Loading OutreachEngine...")
    engine = OutreachEngine(api_key=api_key)

    # 3. Step 1: Classify Route
    print("\n📡 Step 1: Classifying Route from JD...")
    route_details = engine.classify_route(jd_text)
    print(f"   ✓ Route Classification: {route_details.get('route', 'Unknown')}")
    print(f"   ✓ Has Explicit Poster: {route_details.get('has_explicit_poster', False)}")
    if route_details.get('poster_name'):
        print(f"   ✓ Poster Name: {route_details.get('poster_name')} ({route_details.get('poster_title')})")
    print(f"   ✓ Reason: {route_details.get('reason')}")

    # 4. Step 2: Search Proxy for Recruiter/Hiring Managers
    print(f"\n📡 Step 2: Searching DuckDuckGo Proxy for {company_name} LinkedIn Leads...")
    leads = engine.discover_leads(company_name)
    print(f"   ✓ Found {len(leads)} raw search results.")
    for idx, l in enumerate(leads, 1):
        print(f"     [{idx}] {l.get('title')} -> {l.get('url')}")

    # 5. Steps 3 & 4: Parse & Relevance Score
    print("\n📡 Step 3 & 4: Structured Parsing & Relevance Matching...")
    match_result = engine.parse_and_rank_leads(leads, jd_text)
    
    recruiter = match_result.get("recruiter")
    hm = match_result.get("hiring_manager")
    
    if recruiter:
        print(f"   🎯 Plausible Recruiter Found:")
        print(f"      - Name: {recruiter.get('name')}")
        print(f"      - Title: {recruiter.get('title')}")
        print(f"      - LinkedIn: {recruiter.get('linkedin_url')}")
        print(f"      - Plausibility Score: {recruiter.get('plausibility_score')}/5")
        print(f"      - Reason: {recruiter.get('reason')}")
    else:
        print("   ❌ No Plausible Recruiter matched.")
        
    if hm:
        print(f"   🎯 Plausible Hiring Manager Found:")
        print(f"      - Name: {hm.get('name')}")
        print(f"      - Title: {hm.get('title')}")
        print(f"      - LinkedIn: {hm.get('linkedin_url')}")
        print(f"      - Plausibility Score: {hm.get('plausibility_score')}/5")
        print(f"      - Reason: {hm.get('reason')}")
    else:
        print("   ❌ No Plausible Hiring Manager matched.")

    # 6. Step 5: Synthesize humanized outreach pack
    target = hm if hm else (recruiter if recruiter else None)
    if not target:
        print("\n❌ Skipping Step 5: No target matched. Fallback to Route D.")
        sys.exit(0)

    print(f"\n📡 Step 5: Synthesizing Humanized Outreach DM for target '{target.get('name')}'...")
    outreach_pack = engine.generate_outreach_pack(target, user_profile, jd_text, route_details.get("route"))
    
    print("\n" + "=" * 60)
    print("🔥 THE HUMANIZED OUTREACH PACK:")
    print("=" * 60)
    print(f"DM text:\n{outreach_pack.get('outreach_dm')}\n")
    print(f"Exit Line:\n{outreach_pack.get('exit_line')}\n")
    print(f"Email Guesses:\n{outreach_pack.get('email_guesses')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
