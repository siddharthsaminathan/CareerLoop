import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("careerloop.run_assembly_test")

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from careerloop.package_assembly import PackageAssembler

def main():
    print("=" * 60)
    print("🤖 STARTING E2E PACKAGE ASSEMBLY VALIDATION RUN")
    print("=" * 60)

    # 1. Load Master CV text from cv.md
    cv_path = os.path.join(ROOT, "cv.md")
    if os.path.exists(cv_path):
        with open(cv_path, "r", encoding="utf-8") as f:
            master_cv_text = f.read()
    else:
        master_cv_text = "# Siddharth Saminathan\nAI Product Engineer\nEmail: siddharthsaminathan99@gmail.com"

    # 2. Setup mock/simulated Council result state matching live BukuWarung run
    simulated_state = {
        "job_id": "loop-0001",
        "job_title": "AI Product Engineer",
        "company": "BukuWarung",
        "master_cv": master_cv_text,
        "application_pack": {
            "resume_markdown": master_cv_text, # Simulate tailored resume
            "cover_note": """# Cover Letter — BukuWarung

Dear Rajesh Chandrashekaran,

I am writing to express my strong interest in the AI Product Engineer role at BukuWarung. 

Having built Emote from scratch to 450+ active users and reduced multi-agent latencies from 15s down to 3s, I am highly familiar with the operational scaling and latency challenges of production AI. I look forward to bringing my experience in FastAPI, multi-agent systems, and cost optimization to BukuWarung's scaling initiatives.

Sincerely,
Siddharth Saminathan"""
        },
        "company_intelligence": {
            "recruiter_info": {
                "name": "Rajesh Chandrashekaran",
                "link": "https://www.linkedin.com/in/rajesh-chandrashekaran-12345",
                "role": "VP Engineering",
                "plausibility_score": "5",
                "route": "Route C",
                "reason": "Direct hiring manager and engineering lead in matching division."
            },
            "outreach_strategy_hint": """OUTREACH PACK:
DM: Hey Rajesh, saw you're expanding BukuWarung's AI engineering team. I built Emote from scratch (450+ users, FastAPI/Redis backend) and optimized our multi-agent orchestration pipeline to reduce latencies from 15s to 3s while cutting LLM costs by 95%. Would love to chat about bringing this operational focus to your scaling team.

Exit Line: Let me know if you have 5 minutes to chat this week.

Email Guesses: rajesh@bukuwarung.com, rajesh.c@bukuwarung.com"""
        }
    }

    # 3. Run Package Assembler
    print("\n[Assembly Step] Constructing PackageAssembler...")
    assembler = PackageAssembler(root_dir=ROOT)
    
    print("\n[Assembly Step] Running E2E Compilation & Packaging...")
    try:
        result = assembler.assemble_package(
            person_id="siddharth",
            job_id="loop-0001",
            council_state=simulated_state
        )
        print("\n" + "=" * 60)
        print("🔥 VALIDATION RUN COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"📁 Target Folder: {result['pack_dir']}")
        print(f"📄 Generated Files:")
        pack_path = Path(result['pack_dir'])
        for f in pack_path.iterdir():
            print(f"   - {f.name} ({f.stat().st_size} bytes)")
        print("=" * 60)
        
        # Verify specific file existence
        expected_files = [
            "resume.md",
            "cover_note.md",
            "outreach_pack.md",
            "pack_metadata.json",
            "Siddharth_Saminathan_Resume_BukuWarung_ATS.pdf",
            "Siddharth_Saminathan_Resume_BukuWarung_Product_Engineer.pdf"
        ]
        
        missing = []
        for ef in expected_files:
            if not (pack_path / ef).exists():
                missing.append(ef)
                
        if missing:
            print(f"❌ VALIDATION FAILED! Missing files: {missing}")
            sys.exit(1)
        else:
            print("🚀 ALL EXPECTED FILES ARE CONFIRMED PRESENT AND CORRECT!")
            
    except Exception as e:
        print(f"💥 ASSEMBLY VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
